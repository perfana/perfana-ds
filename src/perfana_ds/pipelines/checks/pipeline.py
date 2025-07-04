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

"""Main pipeline orchestrator for the check pipeline."""

import logging
from datetime import datetime
from time import time
from typing import Any

from perfana_ds.catalog.catalog import Catalog, get_catalog
from perfana_ds.schemas.perfana.test_runs import EvaluateStatus, TestRun

from .base import BenchmarkNotFoundError, CheckPipelineError
from .benchmark_comparison import BenchmarkComparator
from .benchmark_matcher import BenchmarkMatcher
from .data_aggregator import DataAggregator
from .requirement_checker import RequirementChecker

logger = logging.getLogger(__name__)


def run_check_pipeline(
    test_run_ids: list[str],
    catalog: Catalog | None = None,
    force_reprocess: bool = False,
    snapshot_id: str | None = None,
    grafana_info: str | None = None,
) -> dict[str, Any]:
    """Run the complete check pipeline for given test run IDs.

    Args:
        test_run_ids: List of test run IDs to process
        catalog: Optional catalog instance (will create new if None)
        force_reprocess: Whether to reprocess existing check results
        snapshot_id: Optional snapshot ID for the check results
        grafana_info: Optional Grafana information

    Returns:
        Dictionary containing pipeline execution results

    Raises:
        CheckPipelineError: If pipeline execution fails
    """
    start_time = time()
    logger.info(f"Starting check pipeline for {len(test_run_ids)} test runs")

    if catalog is None:
        catalog = get_catalog()

    # Initialize services
    benchmark_matcher = BenchmarkMatcher(catalog)
    data_aggregator = DataAggregator(catalog)
    requirement_checker = RequirementChecker(catalog)
    benchmark_comparator = BenchmarkComparator(catalog)

    results = {
        "processed_test_runs": 0,
        "processed_benchmarks": 0,
        "created_check_results": 0,
        "created_compare_results": 0,
        "failed_test_runs": [],
        "execution_time_seconds": 0,
    }

    try:
        for test_run_id in test_run_ids:
            try:
                # Load test run
                test_run = catalog.testRuns.load_object({"testRunId": test_run_id})
                if not test_run:
                    logger.error(f"Test run {test_run_id} not found")
                    results["failed_test_runs"].append(
                        {"test_run_id": test_run_id, "error": "Test run not found"}
                    )
                    continue

                # Delete existing check results if force reprocessing
                if force_reprocess:
                    catalog.checkResults.collection.delete_many(
                        {"testRunId": test_run_id}
                    )
                    logger.info(f"Deleted existing check results for {test_run_id}")

                # Process single test run
                test_run_results = process_single_test_run(
                    test_run=test_run,
                    benchmark_matcher=benchmark_matcher,
                    data_aggregator=data_aggregator,
                    requirement_checker=requirement_checker,
                    benchmark_comparator=benchmark_comparator,
                    catalog=catalog,
                    snapshot_id=snapshot_id,
                    grafana_info=grafana_info,
                )

                results["processed_test_runs"] += 1
                results["processed_benchmarks"] += test_run_results[
                    "processed_benchmarks"
                ]
                results["created_check_results"] += test_run_results[
                    "created_check_results"
                ]
                results["created_compare_results"] += test_run_results[
                    "created_compare_results"
                ]

            except Exception as e:
                logger.error(f"Failed to process test run {test_run_id}: {str(e)}")
                results["failed_test_runs"].append(
                    {"test_run_id": test_run_id, "error": str(e)}
                )

        results["execution_time_seconds"] = time() - start_time
        logger.info(
            f"Check pipeline completed in {results['execution_time_seconds']:.2f}s. "
            f"Processed {results['processed_test_runs']} test runs, "
            f"created {results['created_check_results']} check results, "
            f"created {results['created_compare_results']} compare results"
        )

        return results

    except Exception as e:
        results["execution_time_seconds"] = time() - start_time
        raise CheckPipelineError(f"Check pipeline failed: {str(e)}")


def process_single_test_run(
    test_run: TestRun,
    benchmark_matcher: BenchmarkMatcher,
    data_aggregator: DataAggregator,
    requirement_checker: RequirementChecker,
    benchmark_comparator: BenchmarkComparator,
    catalog: Catalog,
    snapshot_id: str | None = None,
    grafana_info: str | None = None,
) -> dict[str, Any]:
    """Process a single test run through the complete pipeline."""
    logger.info(f"Processing test run {test_run.testRunId}")

    results = {
        "processed_benchmarks": 0,
        "created_check_results": 0,
        "created_compare_results": 0,
        "failed_benchmarks": [],
    }

    # --- STATUS: IN_PROGRESS ---
    now = datetime.utcnow()
    if not test_run.status:
        from perfana_ds.schemas.perfana.test_runs import TestRunStatus

        test_run.status = TestRunStatus()
    test_run.status.evaluatingChecks = EvaluateStatus.IN_PROGRESS
    test_run.status.evaluatingComparisons = EvaluateStatus.IN_PROGRESS
    test_run.status.lastUpdate = now
    catalog.testRuns.collection.update_one(
        {"_id": test_run.id},
        {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
    )

    try:
        # Find matching benchmarks
        benchmarks = benchmark_matcher.find_matching_benchmarks(test_run)
        logger.info(f"Found {len(benchmarks)} matching benchmarks")

        # If no benchmarks with panel.requirement, set status to NOT_CONFIGURED
        if not any(getattr(b.panel, "requirement", None) for b in benchmarks):
            test_run.status.evaluatingChecks = EvaluateStatus.NOT_CONFIGURED
            test_run.status.lastUpdate = datetime.utcnow()
            catalog.testRuns.collection.update_one(
                {"_id": test_run.id},
                {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
            )
            return results

        check_results = []

        for benchmark in benchmarks:
            try:
                # Aggregate metrics data
                aggregation_result = data_aggregator.aggregate_metrics_for_benchmark(
                    test_run, benchmark
                )

                # Create check result
                check_result = requirement_checker.create_check_result(
                    test_run=test_run,
                    benchmark=benchmark,
                    aggregation_result=aggregation_result,
                    grafana_info=grafana_info,
                    snapshot_id=snapshot_id,
                )

                if check_result is not None:
                    # Save to database
                    catalog.checkResults.save_object(check_result)
                    check_results.append(check_result)
                    results["processed_benchmarks"] += 1
                    results["created_check_results"] += 1
                    logger.debug(
                        f"Created check result for benchmark {benchmark.id} "
                        f"(status: {check_result.status})"
                    )

            except Exception as e:
                logger.error(f"Failed to process benchmark {benchmark.id}: {str(e)}")
                results["failed_benchmarks"].append(
                    {"benchmarkId": benchmark.id, "error": str(e)}
                )

        # --- STATUS: ERROR if any checkResult has status ERROR ---
        if any(getattr(cr, "status", None) == "ERROR" for cr in check_results):
            test_run.status.evaluatingChecks = EvaluateStatus.ERROR
            test_run.status.lastUpdate = datetime.utcnow()
            catalog.testRuns.collection.update_one(
                {"_id": test_run.id},
                {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
            )

        # Create compare results after all check results are created
        try:
            compare_results = [
                cr
                for cr in benchmark_comparator.process(test_run, benchmarks)
                if cr is not None
            ]
            # Save compare results to database
            for compare_result in compare_results:
                try:
                    catalog.compareResults.save_object(compare_result)
                    results["created_compare_results"] += 1
                except Exception as save_exc:
                    import traceback

                    logger.error(
                        f"Failed to save compare result for benchmark {getattr(compare_result, 'benchmarkId', None)} in test run {test_run.testRunId}: {str(save_exc)}\n{traceback.format_exc()}"
                    )
        except Exception as e:
            import traceback

            logger.error(
                f"Failed to create compare results for test run {test_run.testRunId}: {str(e)}\n{traceback.format_exc()}"
            )
            logger.error(
                f"Benchmarks for test run {test_run.testRunId}: {[b.id for b in benchmarks]}"
            )

        # --- STATUS: COMPLETE ---
        test_run.status.evaluatingChecks = EvaluateStatus.COMPLETE
        test_run.status.evaluatingComparisons = EvaluateStatus.COMPLETE
        test_run.status.lastUpdate = datetime.utcnow()
        catalog.testRuns.collection.update_one(
            {"_id": test_run.id},
            {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
        )

        # --- CONSOLIDATED RESULT AGGREGATION ---
        from perfana_ds.schemas.perfana.test_runs import ConsolidatedResult

        # CheckResults: meetsRequirement
        check_results = (
            catalog.checkResults.load_objects({"testRunId": test_run.testRunId}) or []
        )
        meets_requirement = all(
            getattr(cr, "meetsRequirement", True) for cr in check_results
        )

        # CompareResults: previous and baseline
        compare_results = (
            catalog.compareResults.load_objects({"testRunId": test_run.testRunId}) or []
        )
        prev_ok = True
        baseline_ok = True
        for cr in compare_results:
            label = getattr(cr, "label", "")
            meets = getattr(cr, "meetsRequirement", True)
            if (
                label
                and label.startswith("Compared to previous test run")
                and not meets
            ):
                prev_ok = False
            if label and label.startswith("Compared to fixed baseline") and not meets:
                baseline_ok = False
        overall = meets_requirement and prev_ok and baseline_ok
        consolidated = ConsolidatedResult(
            meetsRequirement=meets_requirement,
            benchmarkPreviousTestRunOK=prev_ok,
            benchmarkBaselineTestRunOK=baseline_ok,
            overall=overall,
        )
        catalog.testRuns.collection.update_one(
            {"_id": test_run.id},
            {"$set": {"consolidatedResult": consolidated.model_dump(by_alias=True)}},
        )

        return results

    except BenchmarkNotFoundError as e:
        logger.warning(
            f"No benchmarks found for test run {test_run.testRunId}: {str(e)}"
        )
        test_run.status.evaluatingChecks = EvaluateStatus.NOT_CONFIGURED
        test_run.status.lastUpdate = datetime.utcnow()
        catalog.testRuns.collection.update_one(
            {"_id": test_run.id},
            {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
        )
        return results

    except Exception as e:
        test_run.status.evaluatingChecks = EvaluateStatus.ERROR
        test_run.status.lastUpdate = datetime.utcnow()
        catalog.testRuns.collection.update_one(
            {"_id": test_run.id},
            {"$set": {"status": test_run.status.model_dump(by_alias=True)}},
        )
        raise CheckPipelineError(
            f"Failed to process test run {test_run.testRunId}: {str(e)}"
        )
