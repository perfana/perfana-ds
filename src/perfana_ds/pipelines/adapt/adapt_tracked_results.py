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
from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.pipelines.adapt.adapt_input import _statistics_differences_pipeline
from perfana_ds.pipelines.adapt.adapt_results import _adapt_result_pipeline

logger = get_task_logger(__name__)


def aggregate_adapt_tracked_results(test_run_ids: list[str]):
    logger.info(f"Aggregating tracked ADAPT results for {len(test_run_ids)} test runs")
    start_time = time()
    test_run_ids = list(set(test_run_ids))
    if len(test_run_ids) == 0:
        raise ValueError("No test runs passed to function.")

    catalog = get_catalog()
    # load one test run to match application, testEnvironment and testType
    test_run = catalog.testRuns.load_object({"testRunId": test_run_ids[0]})
    if test_run is None:
        raise FileNotFoundError(f"No test run found for id {test_run_ids[0]}")

    filter_pipe = [{"$match": {"controlGroupId": {"$in": test_run_ids}}}]
    tracked_results_input_pipe = _create_tracked_results_input_pipe(
        adapt_results_dataset=catalog.ds.adaptResults
    )
    output_pipe = [
        {
            "$merge": {
                "into": catalog.ds.adaptTrackedResults.collection_name,
                "on": catalog.ds.adaptTrackedResults.upsert_fields,
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]

    pipe = (
        filter_pipe
        + tracked_results_input_pipe
        + _statistics_differences_pipeline(
            control_group_statistics_dataset=catalog.ds.controlGroupStatistics,
            test_run=test_run,
        )
        + _adapt_result_pipeline(test_run)
        + output_pipe
    )

    # print("aggregate_adapt_tracked_results: " + str(pipe))

    _ = catalog.ds.controlGroup.collection.aggregate(pipe)

    output_counts = catalog.ds.adaptTrackedResults.collection.count_documents(
        {"testRunId": {"$in": test_run_ids}}
    )
    logger.info(
        f"Finished ADAPT tracked results for {output_counts} metrics in {(time() - start_time):.2f} seconds"
    )
    return True


def _create_tracked_results_input_pipe(adapt_results_dataset: MongoData):
    """Aggregation pipeline to be applied to dsControlGroups collection.

    Creates the ADAPT input data for tracked test runs that need to be re-evaluated
    with the data of the current test runs. The output is the same as dsAdaptInput,
    but for tracked test runs. For tracked test runs we do not store the ADAPT input
    in a collection, therefore this aggregation pipeline creates the entire input
    in one long pipe.
    """
    return [
        # Create doc for each test run id in the testRuns field of a controlgroup
        # {"$unwind": "$testRuns"},  # refers to dsControlGroups.testRuns array field of test run ids
        # find test runs in current control group that need to be tracked
        {
            "$lookup": {
                "from": "testRuns",
                "let": {"testRunIds": "$testRuns"},
                # Track test runs if they are in the control group and
                # differences are not accepted, or if in baselineMode
                # Always ignore run if in debug mode
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$in": ["$testRunId", "$$testRunIds"]},
                                ]
                            },
                            "adapt.differencesAccepted": {"$ne": "ACCEPTED"},
                            "adapt.mode": {"$ne": "DEBUG"},
                        }
                    },
                    {
                        "$project": {
                            "testRunId": 1,
                            "adapt": 1,
                            "testRunStart": "$start",
                        }
                    },
                ],
                "as": "trackedTestRuns",
            }
        },
        # {"$unwind": "$trackedTestRuns"},
        {
            "$project": {
                "testRunId": "$controlGroupId",  # TODO: use testRunId for control groups
                "trackedTestRunIds": "$trackedTestRuns.testRunId",
            }
        },
        # for each matched test run, lookup adapt results with concluded differences
        {
            "$lookup": {
                "from": adapt_results_dataset.collection_name,
                "let": {"testRunIds": "$trackedTestRunIds"},
                "pipeline": [
                    {"$match": {"$expr": {"$in": ["$testRunId", "$$testRunIds"]}}},
                    {
                        "$match": {
                            "conclusion.label": {
                                "$in": [
                                    "increase",
                                    "decrease",
                                    "regression",
                                    "improvement",
                                ]
                            },
                            "conclusion.ignore": False,
                        }
                    },
                    {
                        "$project": {
                            "conclusion": 1,
                            "controlGroupId": 1,
                            "testRunId": 1,
                            "applicationDashboardId": 1,
                            "panelId": 1,
                            "metricName": 1,
                        }
                    },
                ],
                "as": "trackedResults",
            }
        },
        # Create a document for each metric in tracked test runs that needs to be re-evaluated
        {"$unwind": "$trackedResults"},
        # Lookup metric statistics for each metric, for the currently selected test runs
        {
            "$lookup": {
                "from": "dsMetricStatistics",
                "let": {
                    "testRunId": "$testRunId",
                    "applicationDashboardId": "$trackedResults.applicationDashboardId",
                    "panelId": "$trackedResults.panelId",
                    "metricName": "$trackedResults.metricName",
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$testRunId", "$$testRunId"]},
                                    {
                                        "$eq": [
                                            "$applicationDashboardId",
                                            "$$applicationDashboardId",
                                        ]
                                    },
                                    {"$eq": ["$panelId", "$$panelId"]},
                                    {"$eq": ["$metricName", "$$metricName"]},
                                ]
                            }
                        }
                    },
                ],
                "as": "metricStatistics",
            }
        },
        # Expect array of length 1 if present, empty otherwise.
        # Unwinding empty array will drop the document, which is Good because
        # we do not re-evaluate previous metrics that do not exist in the current
        # test run.
        {"$unwind": "$metricStatistics"},
        # Add fields to merged metricStatistics before making it the root document
        {
            "$addFields": {
                "metricStatistics": {
                    "trackedDifferenceId": "$trackedResults._id",
                    "trackedTestRunId": "$trackedResults.testRunId",
                    "trackedConclusion": "$trackedResults.conclusion",
                    "controlGroupId": "$trackedResults.controlGroupId",
                }
            }
        },
        {"$replaceRoot": {"newRoot": "$metricStatistics"}},
    ]
