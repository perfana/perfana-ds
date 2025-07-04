# Copyright 2025 Perfana Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from time import time

from celery.utils.log import get_task_logger

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.pipelines.adapt.adapt_conclusion import aggregate_adapt_conclusion
from perfana_ds.pipelines.adapt.adapt_input import aggregate_adapt_input
from perfana_ds.pipelines.adapt.adapt_results import aggregate_adapt_results
from perfana_ds.pipelines.adapt.adapt_tracked_results import (
    aggregate_adapt_tracked_results,
)
from perfana_ds.pipelines.adapt.backfill_missing_metrics import (
    backfill_missing_metrics_async,
)
from perfana_ds.pipelines.control_groups.pipeline import run_control_groups_pipeline
from perfana_ds.schemas.perfana.test_runs import EvaluateStatus

logger = get_task_logger(__name__)


def run_adapt_pipeline(  # noqa: PLR0912, too many branches
    test_run_ids: list[str],
    create_control_group: bool = True,
    calculate_statistics: bool = True,
    evaluate_results: bool = True,
    create_conclusion: bool = True,
    reevaluate_tracked_results: bool = True,
):
    logger.info(f"Starting ADAPT analysis for {test_run_ids}")
    start_time = time()
    test_run_ids = list(set(test_run_ids))
    if len(test_run_ids) == 0:
        raise ValueError("No test runs passed to function.")

    catalog = get_catalog()
    test_run = catalog.testRuns.load_object({"testRunId": test_run_ids[0]})
    if test_run is None:
        raise FileNotFoundError(
            f"Test run {test_run_ids[0]} not found in {catalog.testRuns.collection_name}"
        )

    # Set evaluatingAdapt to IN_PROGRESS for all test_run_ids
    for test_run_id in test_run_ids:
        tr = catalog.testRuns.load_object({"testRunId": test_run_id})
        if tr and tr.status:
            tr.status.evaluatingAdapt = EvaluateStatus.IN_PROGRESS
            catalog.testRuns.collection.update_one(
                {"_id": tr.id},
                {"$set": {"status": tr.status.model_dump(by_alias=True)}},
            )

    ds_change_points = catalog.ds.changePoints.load_objects(
        {
            "application": test_run.application,
            "testType": test_run.testType,
            "testEnvironment": test_run.testEnvironment,
        },
        sort=[("start", -1)],
    )

    if ds_change_points is not None:
        logger.info(f"Found changepoint for test run {ds_change_points[0].test_run_id}")
        test_run_ids_excluding_changepoint = [
            test_run_id
            for test_run_id in test_run_ids
            if test_run_id != ds_change_points[0].test_run_id
        ]
    else:
        test_run_ids_excluding_changepoint = test_run_ids

    if create_control_group is True:
        control_groups = run_control_groups_pipeline(test_run_ids=test_run_ids)
    else:
        logger.info(f"Loading control group for runs {test_run_ids}")
        control_groups = catalog.ds.controlGroup.load_objects(
            {"controlGroupId": {"$in": test_run_ids}}
        )
        if len(control_groups) != len(test_run_ids):
            raise FileNotFoundError(
                f"Could not match an existing control group for all runs in {test_run_ids}"
            )
        logger.info(f"Loaded control groups for {len(test_run_ids)} runs")

    # Check for empty control groups and set NO_BASELINES_FOUND status
    test_runs_with_no_baselines = []
    for control_group in control_groups:
        # Check if control group has no test runs (common when test run is a changepoint)
        control_group_empty = False
        
        if hasattr(control_group, 'n_test_runs') and control_group.n_test_runs == 0:
            control_group_empty = True
        elif hasattr(control_group, 'test_runs') and len(control_group.test_runs) == 0:
            control_group_empty = True
        elif hasattr(control_group, 'nTestRuns') and control_group.nTestRuns == 0:  # Alternative field name
            control_group_empty = True
        elif hasattr(control_group, 'testRuns') and len(control_group.testRuns) == 0:  # Alternative field name
            control_group_empty = True
            
        if control_group_empty:
            test_runs_with_no_baselines.append(control_group.control_group_id)
            logger.info(f"Control group for test run {control_group.control_group_id} is empty - likely due to changePoint")

    if test_runs_with_no_baselines:
        logger.info(f"Found {len(test_runs_with_no_baselines)} test runs with empty control groups: {test_runs_with_no_baselines}")
        
        # Set status to NO_BASELINES_FOUND for test runs with empty control groups
        for test_run_id in test_runs_with_no_baselines:
            tr = catalog.testRuns.load_object({"testRunId": test_run_id})
            if tr and tr.status:
                tr.status.evaluatingAdapt = EvaluateStatus.NO_BASELINES_FOUND
                catalog.testRuns.collection.update_one(
                    {"_id": tr.id},
                    {"$set": {"status": tr.status.model_dump(by_alias=True)}},
                )
                logger.info(f"Set evaluatingAdapt status to NO_BASELINES_FOUND for test run {test_run_id}")
        
        # Remove test runs with no baselines from further processing
        test_run_ids = [tid for tid in test_run_ids if tid not in test_runs_with_no_baselines]
        test_run_ids_excluding_changepoint = [tid for tid in test_run_ids_excluding_changepoint if tid not in test_runs_with_no_baselines]
        
        if not test_run_ids:
            logger.info("All test runs have empty control groups - skipping ADAPT analysis")
            return True

    if calculate_statistics is True or create_control_group is True:
        catalog.ds.adaptInput.collection.delete_many(
            {"testRunId": {"$in": test_run_ids}}
        )
        adapt_input_result = aggregate_adapt_input(test_run_ids=test_run_ids)

        # Store metrics that need backfilling for later (after ADAPT analysis)
        metrics_needing_backfill = None
        control_group_test_run_ids_for_backfill = None

        if isinstance(adapt_input_result, list) and adapt_input_result:
            logger.info(
                f"Found {len(adapt_input_result)} metrics using default values - will trigger backfill after ADAPT analysis"
            )

            # Get control group test run IDs for backfilling
            control_group_test_run_ids = []
            for control_group in control_groups:
                if hasattr(control_group, "test_runs"):
                    control_group_test_run_ids.extend(control_group.test_runs)
                elif hasattr(control_group, "testRuns"):
                    control_group_test_run_ids.extend(control_group.testRuns)

            logger.info(
                f"All control group test runs for backfill: {control_group_test_run_ids}"
            )

            # Remove duplicates but keep all historical test runs for backfill
            # These historical test runs need dsControlGroupStatistics and dsAdaptResults
            # created for metrics that didn't have default values when they originally ran
            control_group_test_run_ids = list(set(control_group_test_run_ids))
            logger.info(
                f"Unique control group test runs available for backfill: {control_group_test_run_ids}"
            )

            if control_group_test_run_ids:
                # Store for backfill after ADAPT analysis
                metrics_needing_backfill = adapt_input_result
                control_group_test_run_ids_for_backfill = control_group_test_run_ids
                logger.info(
                    f"Stored {len(control_group_test_run_ids)} control group test runs for backfill after ADAPT analysis"
                )
            else:
                logger.info("No control group test runs to backfill")

    if evaluate_results:
        catalog.ds.adaptResults.collection.delete_many(
            {"testRunId": {"$in": test_run_ids}}
        )
        if len(test_run_ids_excluding_changepoint) > 0:
            logger.info(
                f"Starting aggregate_adapt_results for {len(test_run_ids)} test run IDs"
            )
            logger.info(
                f"Test run IDs excluding changepoint: {test_run_ids_excluding_changepoint}"
            )

            _ = aggregate_adapt_results(test_run_ids=test_run_ids)

            # Check dsAdaptResults count after running
            adapt_results_count = catalog.ds.adaptResults.collection.count_documents(
                {"testRunId": {"$in": test_run_ids}}
            )
            logger.info(
                f"dsAdaptResults contains {adapt_results_count} documents after aggregate_adapt_results"
            )
        else:
            logger.info(
                "Skipping aggregate_adapt_results - no test runs excluding changepoint"
            )

    if reevaluate_tracked_results:
        catalog.ds.adaptTrackedResults.collection.delete_many(
            {"testRunId": {"$in": test_run_ids}}
        )
        if len(test_run_ids_excluding_changepoint) > 0:
            _ = aggregate_adapt_tracked_results(
                test_run_ids=test_run_ids_excluding_changepoint
            )

    if create_conclusion:
        if ds_change_points is not None:
            catalog.ds.adaptConclusion.save_object(
                {
                    "testRunId": ds_change_points[0].test_run_id,
                    "controlGroupId": ds_change_points[0].test_run_id,
                    "updatedAt": time(),
                    "regressions": [],
                    "improvements": [],
                    "differences": [],
                    "trackedRegressions": [],
                    "conclusion": "SKIPPED",
                    "details": {
                        "message": "Test run is changepoint skipping ADAPT conclusion"
                    },
                }
            )

        _ = aggregate_adapt_conclusion(test_run_ids=test_run_ids_excluding_changepoint)

        # After adapt conclusion, set evaluatingAdapt to COMPLETE and update consolidatedResult.adaptTestRunOK
        for test_run_id in test_run_ids_excluding_changepoint:
            tr = catalog.testRuns.load_object({"testRunId": test_run_id})
            if tr:
                # Update status
                if tr.status:
                    tr.status.evaluatingAdapt = EvaluateStatus.COMPLETE
                    catalog.testRuns.collection.update_one(
                        {"_id": tr.id},
                        {"$set": {"status": tr.status.model_dump(by_alias=True)}},
                    )
                # Update consolidatedResult.adaptTestRunOK and .overall
                conclusion_doc = catalog.ds.adaptConclusion.collection.find_one(
                    {"testRunId": test_run_id}
                )
                adapt_ok = True
                if conclusion_doc:
                    if conclusion_doc.get("conclusion") == "REGRESSION":
                        adapt_ok = False
                    # PASSED or SKIPPED = True
                # Update consolidatedResult
                consolidated = (
                    tr.consolidatedResult.model_dump(by_alias=True)
                    if tr.consolidatedResult
                    else {}
                )
                consolidated["adaptTestRunOK"] = adapt_ok
                # overall = all 4 keys True
                overall = all(
                    [
                        consolidated.get("meetsRequirement", True),
                        consolidated.get("benchmarkPreviousTestRunOK", True),
                        consolidated.get("benchmarkBaselineTestRunOK", True),
                        adapt_ok,
                    ]
                )
                consolidated["overall"] = overall
                catalog.testRuns.collection.update_one(
                    {"_id": tr.id}, {"$set": {"consolidatedResult": consolidated}}
                )

    # Trigger backfill after all ADAPT analysis is complete
    if metrics_needing_backfill and control_group_test_run_ids_for_backfill:
        logger.info("Starting backfill after ADAPT analysis completion")
        try:
            backfill_missing_metrics_async(
                control_group_test_run_ids=control_group_test_run_ids_for_backfill,
                metrics_using_defaults=metrics_needing_backfill,
            )
            logger.info(
                f"Backfill completed after ADAPT analysis for {len(control_group_test_run_ids_for_backfill)} control group test runs"
            )
        except Exception as e:
            logger.error(f"Failed to trigger backfill after ADAPT analysis: {e}")

    logger.info(
        f"Finished ADAPT for {len(test_run_ids)} runs in {(time() - start_time):.2f} seconds"
    )
    return True
