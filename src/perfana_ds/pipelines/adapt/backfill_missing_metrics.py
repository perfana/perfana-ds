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

from datetime import datetime
from time import time
from typing import Any

from celery.utils.log import get_task_logger

from perfana_ds.catalog.catalog import get_catalog

logger = get_task_logger(__name__)


def backfill_missing_metrics_async(
    control_group_test_run_ids: list[str], metrics_using_defaults: list[dict[str, Any]]
):
    """
    Async function to backfill missing dsMetricStatistics documents
    when defaultValueIfControlGroupMissing is used.

    Args:
        control_group_test_run_ids: List of test run IDs in the control group
        metrics_using_defaults: List of metrics that used default values, each containing:
            - applicationDashboardId
            - panelId
            - metricName
            - defaultValue
            - dashboardUid
            - dashboardLabel
            - panelTitle
            - unit (optional)
    """
    logger.info(
        f"Backfilling {len(metrics_using_defaults)} metrics for {len(control_group_test_run_ids)} control group test runs"
    )
    logger.info(f"Control group test runs: {control_group_test_run_ids}")
    logger.info(
        f"Metrics to backfill: {[metric['metricName'] for metric in metrics_using_defaults]}"
    )
    start_time = time()

    catalog = get_catalog()
    control_group_statistics_dataset = catalog.ds.controlGroupStatistics
    adapt_results_dataset = catalog.ds.adaptResults

    # Get test run info to extract testRunStart
    test_run_info = {}
    for test_run_id in control_group_test_run_ids:
        test_run = catalog.testRuns.load_object({"testRunId": test_run_id})
        if test_run:
            test_run_info[test_run_id] = test_run.start
            logger.debug(
                f"Found test run {test_run_id} with start time {test_run.start}"
            )
        else:
            logger.warning(f"Could not find test run info for {test_run_id}")
            test_run_info[test_run_id] = None

    documents_to_insert = []
    adapt_results_to_insert = []
    documents_skipped = 0
    adapt_results_skipped = 0

    for test_run_id in control_group_test_run_ids:
        logger.debug(f"Processing test run {test_run_id}")
        for metric_info in metrics_using_defaults:
            # Extract default value once for both document types
            default_value = metric_info["defaultValue"]

            # Check if document already exists in dsControlGroupStatistics
            query = {
                "controlGroupId": test_run_id,  # Note: controlGroupId, not testRunId
                "applicationDashboardId": metric_info["applicationDashboardId"],
                "panelId": metric_info["panelId"],
                "metricName": metric_info["metricName"],
            }
            existing = control_group_statistics_dataset.collection.find_one(query)

            logger.info(f"Checking dsControlGroupStatistics query: {query}")
            logger.info(
                f"Checking dsControlGroupStatistics for test run {test_run_id}, metric {metric_info['metricName']}: {'EXISTS' if existing else 'MISSING'}"
            )

            if existing:
                logger.info(
                    f"Existing document found: _backfilled={existing.get('_backfilled')}, mean={existing.get('mean')}, _backfilledReason={existing.get('_backfilledReason')}"
                )

            if existing is None:
                logger.debug(
                    f"Creating backfill document for {metric_info['metricName']} in control group {test_run_id}"
                )
                # Create complete dsControlGroupStatistics document with all fields set to default value

                doc = {
                    "controlGroupId": test_run_id,  # This is the key difference from dsMetricStatistics
                    "applicationDashboardId": metric_info["applicationDashboardId"],
                    "panelId": metric_info["panelId"],
                    "metricName": metric_info["metricName"],
                    "dashboardUid": metric_info.get("dashboardUid"),
                    "dashboardLabel": metric_info.get("dashboardLabel"),
                    "panelTitle": metric_info.get("panelTitle"),
                    "unit": metric_info.get("unit"),
                    # All statistical fields set to default value
                    "mean": default_value,
                    "median": default_value,
                    "min": default_value,
                    "max": default_value,
                    "std": 0.0,  # Standard deviation is 0 for constant values
                    "iqr": 0.0,  # IQR is 0 for constant values
                    "idr": 0.0,  # IDR is 0 for constant values
                    "q10": default_value,
                    "q25": default_value,
                    "q75": default_value,
                    "q90": default_value,
                    "q95": default_value,
                    "q99": default_value,
                    # Count fields
                    "n": 1,  # At least 1 observation (the default)
                    "nMissing": 0,
                    "pctMissing": 0.0,
                    "nNonZero": 1 if default_value != 0 else 0,
                    # Flags
                    "isConstant": True,  # Default values are constant
                    "allMissing": False,
                    # Required fields
                    "testRunStart": test_run_info.get(test_run_id),
                    # Metadata
                    "updatedAt": datetime.utcnow(),  # Use proper datetime object
                    # Mark as backfilled
                    "_backfilled": True,
                    "_backfilledReason": "defaultValueIfControlGroupMissing",
                    "_backfilledDefaultValue": default_value,
                }

                documents_to_insert.append(doc)
            else:
                documents_skipped += 1
                logger.debug(
                    f"Document already exists for {metric_info['metricName']} in control group {test_run_id}"
                )

            # Also create dsAdaptResults document for trend visualization
            adapt_query = {
                "testRunId": test_run_id,
                "applicationDashboardId": metric_info["applicationDashboardId"],
                "panelId": metric_info["panelId"],
                "metricName": metric_info["metricName"],
            }
            adapt_result_existing = adapt_results_dataset.collection.find_one(
                adapt_query
            )

            logger.info(f"Checking dsAdaptResults query: {adapt_query}")
            logger.info(
                f"Checking dsAdaptResults for test run {test_run_id}, metric {metric_info['metricName']}: {'EXISTS' if adapt_result_existing else 'MISSING'}"
            )

            if adapt_result_existing is None:
                logger.info(
                    f"Creating dsAdaptResults document for {metric_info['metricName']} in test run {test_run_id}"
                )
                logger.info(
                    f"Document will have panelTitle='{metric_info.get('panelTitle')}', dashboardLabel='{metric_info.get('dashboardLabel')}'"
                )

                adapt_result_doc = {
                    "testRunId": test_run_id,
                    "controlGroupId": test_run_id,  # Self-referencing for control group runs
                    "applicationDashboardId": metric_info["applicationDashboardId"],
                    "panelId": metric_info["panelId"],
                    "metricName": metric_info["metricName"],
                    "dashboardUid": metric_info.get("dashboardUid"),
                    "dashboardLabel": metric_info.get("dashboardLabel"),
                    "panelTitle": metric_info.get("panelTitle"),
                    "unit": metric_info.get("unit"),
                    # Required fields for dsAdaptResults
                    "testRunStart": test_run_info.get(test_run_id),
                    # Default compare config (required field)
                    "compareConfig": {
                        "statistic": {"value": "median", "source": "default"},
                        "iqrThreshold": {"value": 2.0, "source": "default"},
                        "pctThreshold": {"value": 0.15, "source": "default"},
                        "absThreshold": {"value": None, "source": "default"},
                        "nThreshold": {"value": 5, "source": "default"},
                        "ignore": {"value": False, "source": "default"},
                        "defaultValueIfControlGroupMissing": {
                            "value": default_value,
                            "source": "default",
                        },
                    },
                    # Metric classification (required field)
                    "metricClassification": {
                        "_id": None,
                        "metricClassification": None,
                        "higherIsBetter": None,
                    },
                    # Conditions (required field) - all true for valid default value comparison
                    "conditions": {
                        "enoughObservations": True,
                        "notAllMissing": True,
                        "controlNotConstant": False,  # Control is constant (default value)
                        "controlConstant": True,  # Control is constant (default value)
                        "controlNotZero": default_value != 0,
                        "controlExists": True,
                        "hasAbsCheck": False,  # No absolute threshold by default
                        "iqrNotZero": False,  # IQR is 0 for constant values
                    },
                    # Dummy statistical comparisons (all using default value, no differences)
                    "statistic": {
                        "name": "median",  # Default statistic
                        "test": default_value,
                        "control": default_value,
                        "diff": 0.0,
                        "pctDiff": 0.0,
                        "absDiff": 0.0,
                        "iqrDiff": 0.0,
                    },
                    # Thresholds (not applicable for "no difference")
                    "thresholds": {
                        "upper": {
                            "pct": default_value,
                            "iqr": default_value,
                            "abs": default_value,
                            "constant": default_value,
                            "overall": default_value,
                        },
                        "lower": {
                            "pct": default_value,
                            "iqr": default_value,
                            "abs": default_value,
                            "constant": default_value,
                            "overall": default_value,
                        },
                    },
                    # All checks show no difference
                    "checks": {
                        "pct": {
                            "valid": True,
                            "increase": False,
                            "decrease": False,
                            "isDifference": False,
                            "observedDiff": 0.0,
                            "invalidReasons": [],
                        },
                        "iqr": {
                            "valid": True,
                            "increase": False,
                            "decrease": False,
                            "isDifference": False,
                            "observedDiff": 0.0,
                            "invalidReasons": [],
                        },
                        "abs": {
                            "valid": True,
                            "increase": False,
                            "decrease": False,
                            "isDifference": False,
                            "observedDiff": 0.0,
                            "invalidReasons": [],
                        },
                        "constant": {
                            "valid": True,
                            "increase": False,
                            "decrease": False,
                            "isDifference": False,
                            "observedDiff": 0.0,
                            "invalidReasons": [],
                        },
                    },
                    # Conclusion: no difference
                    "conclusion": {
                        "valid": True,
                        "partialDifference": False,
                        "allDifference": False,
                        "increase": False,
                        "decrease": False,
                        "ignore": False,
                        "label": "no difference",
                    },
                    # Metadata
                    "updatedAt": datetime.utcnow(),
                    # Mark as backfilled
                    "_backfilled": True,
                    "_backfilledReason": "defaultValueIfControlGroupMissing_trend",
                    "_backfilledDefaultValue": default_value,
                }

                adapt_results_to_insert.append(adapt_result_doc)
                logger.info(
                    f"Prepared dsAdaptResults document: testRunId={test_run_id}, metricName={metric_info['metricName']}, panelTitle={adapt_result_doc.get('panelTitle')}, dashboardLabel={adapt_result_doc.get('dashboardLabel')}"
                )
                logger.info(f"Complete dsAdaptResults document: {adapt_result_doc}")
            else:
                adapt_results_skipped += 1
                logger.debug(
                    f"dsAdaptResults document already exists for {metric_info['metricName']} in test run {test_run_id}"
                )

    logger.info(
        f"Prepared {len(documents_to_insert)} dsControlGroupStatistics documents for insertion, {documents_skipped} already existed"
    )
    logger.info(
        f"Prepared {len(adapt_results_to_insert)} dsAdaptResults documents for insertion, {adapt_results_skipped} already existed"
    )

    # Insert dsControlGroupStatistics documents
    if documents_to_insert:
        try:
            logger.info(
                f"Attempting to insert {len(documents_to_insert)} documents into dsControlGroupStatistics"
            )
            result = control_group_statistics_dataset.collection.insert_many(
                documents_to_insert
            )
            logger.info(
                f"Successfully backfilled {len(result.inserted_ids)} dsControlGroupStatistics documents"
            )
        except Exception as e:
            logger.error(f"Failed to insert dsControlGroupStatistics documents: {e}")
            raise
    else:
        logger.info(
            "No dsControlGroupStatistics backfill needed - all documents already exist"
        )

    # Insert dsAdaptResults documents
    if adapt_results_to_insert:
        try:
            logger.info(
                f"Attempting to insert {len(adapt_results_to_insert)} documents into dsAdaptResults"
            )
            logger.info(f"Full documents to insert: {adapt_results_to_insert}")

            result = adapt_results_dataset.collection.insert_many(
                adapt_results_to_insert
            )

            logger.info(f"MongoDB insert_many result: {result}")
            logger.info(f"Acknowledged: {result.acknowledged}")
            logger.info(f"Number of inserted IDs: {len(result.inserted_ids)}")
            logger.info(f"Inserted document IDs: {result.inserted_ids}")
            logger.info(
                f"Successfully backfilled {len(result.inserted_ids)} dsAdaptResults documents for trend visualization"
            )

            # Verify insertion by counting documents that match our criteria
            verification_count = adapt_results_dataset.collection.count_documents(
                {
                    "testRunId": {"$in": control_group_test_run_ids},
                    "metricName": {
                        "$in": [
                            metric["metricName"] for metric in metrics_using_defaults
                        ]
                    },
                    "_backfilled": True,
                }
            )
            logger.info(
                f"Verification: Found {verification_count} backfilled dsAdaptResults documents in database"
            )

            # Also verify by specific document lookup
            for doc in adapt_results_to_insert:
                found_doc = adapt_results_dataset.collection.find_one(
                    {
                        "testRunId": doc["testRunId"],
                        "metricName": doc["metricName"],
                        "panelId": doc["panelId"],
                    }
                )
                logger.info(
                    f"Verification lookup for testRunId={doc['testRunId']}, metricName={doc['metricName']}: {'FOUND' if found_doc else 'NOT FOUND'}"
                )
                if found_doc:
                    logger.info(
                        f"Found document _id: {found_doc.get('_id')}, _backfilled: {found_doc.get('_backfilled')}"
                    )

        except Exception as e:
            logger.error(f"Failed to insert dsAdaptResults documents: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    else:
        logger.info("No dsAdaptResults backfill needed - all documents already exist")

    total_inserted = len(documents_to_insert) + len(adapt_results_to_insert)
    logger.info(
        f"Backfill completed in {(time() - start_time):.2f} seconds - total documents created: {total_inserted}"
    )

    return total_inserted
