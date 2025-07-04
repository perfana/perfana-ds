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

import time

from celery.utils.log import get_task_logger

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.schemas.control_groups import ControlGroup

logger = get_task_logger(__name__)


def wait_until_test_runs_are_ready(
    test_runs_dataset: MongoData, test_run_ids: list[str]
):
    MAX_RETRIES = 120
    for attempt in range(MAX_RETRIES):
        cursor = test_runs_dataset.collection.find(
            {
                "testRunId": {"$in": test_run_ids},
                "status.evaluatingChecks": {
                    "$nin": ["COMPLETE", "ERROR", "NOT_CONFIGURED"]
                },
            }
        )
        test_runs_in_progress = list(cursor)

        # return if all test runs are
        if len(test_runs_in_progress) == 0:
            break

        logger.info(
            f"Wait for perfana-check to evaluate all test runs (Attempt {attempt})"
        )
        time.sleep(1)
    else:
        raise TimeoutError(
            f"Timeout waiting for all test runs to evaluate checks. {test_run_ids=}"
        )

    # if all test runs are evaluated within the allowed retries.
    return True


def aggregate_control_groups(test_run_ids: list[str]) -> list[ControlGroup]:
    catalog = get_catalog()
    test_runs_dataset = catalog.testRuns
    changepoints_dataset = catalog.ds.changePoints
    control_groups_dataset = catalog.ds.controlGroup

    # wait until perfana-check is ready
    wait_until_test_runs_are_ready(test_runs_dataset, test_run_ids=test_run_ids)

    aggregation_pipe = [
        {"$match": {"testRunId": {"$in": test_run_ids}}},
        {
            "$lookup": {
                "from": changepoints_dataset.collection_name,
                "let": {"testRun": "$$ROOT"},
                "pipeline": [
                    # Find all changepoints for same test group
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$application", "$$testRun.application"]},
                                    {"$eq": ["$testType", "$$testRun.testType"]},
                                    {
                                        "$eq": [
                                            "$testEnvironment",
                                            "$$testRun.testEnvironment",
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    # Find testRun corresponding to each changepoint
                    {
                        "$lookup": {
                            "from": test_runs_dataset.collection_name,
                            "localField": "testRunId",
                            "foreignField": "testRunId",
                            "as": "changepointRun",
                        }
                    },
                    {"$addFields": {"changepointRun": {"$first": "$changepointRun"}}},
                    # Only changepoints Before or Equal to the current run
                    {
                        "$match": {
                            "$expr": {
                                "$lte": ["$changepointRun.start", "$$testRun.start"]
                            }
                        }
                    },
                    {"$sort": {"changepointRun.start": -1}},
                    # Only the last changepoint is kept
                    {"$limit": 1},
                    {"$addFields": {"start": "$changepointRun.start"}},
                    # {"$project": {"changepointRun": 0}},
                ],
                "as": "changePoint",
            }
        },
        {"$addFields": {"changePoint": {"$first": "$changePoint"}}},
        {
            "$lookup": {
                "from": test_runs_dataset.collection_name,
                "let": {"testRun": "$$ROOT"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$application", "$$testRun.application"]},
                                    {"$eq": ["$testType", "$$testRun.testType"]},
                                    {
                                        "$eq": [
                                            "$testEnvironment",
                                            "$$testRun.testEnvironment",
                                        ]
                                    },
                                    {"$lt": ["$start", "$$testRun.start"]},
                                    {"$gte": ["$start", "$$testRun.changePoint.start"]},
                                    {"$ne": ["$adapt.differencesAccepted", "DENIED"]},
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    "$consolidatedResult.meetsRequirement",
                                                    True,
                                                ]
                                            },
                                            {"$eq": ["$adapt.mode", "BASELINE"]},
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {"$sort": {"start": -1}},
                    {"$limit": 10},
                    # {"$project": {"testRunId": 1}}
                ],
                "as": "controlRuns",
            }
        },
        {
            "$project": {
                "_id": 0,
                "controlGroupId": "$testRunId",
                "application": 1,
                "testType": 1,
                "testEnvironment": 1,
                "testRuns": "$controlRuns.testRunId",
                "nTestRuns": {"$size": "$controlRuns"},
                "firstDatetime": {"$min": "$controlRuns.start"},
                "lastDatetime": {"$max": "$controlRuns.start"},
                "changePoint": {
                    "testRunId": "$changePoint.testRunId",
                    "start": "$changePoint.start",
                },
                "updatedAt": "$$NOW",
            }
        },
    ]

    output_pipe = [
        {
            "$merge": {
                "into": control_groups_dataset.collection_name,
                "on": control_groups_dataset.upsert_fields,
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]

    pipeline = aggregation_pipe + output_pipe
    # print("aggregate_control_groups: " + str(pipeline))

    _ = test_runs_dataset.collection.aggregate(pipeline)

    control_groups = control_groups_dataset.load_objects(
        {"controlGroupId": {"$in": test_run_ids}}
    )
    return control_groups


# def create_control_group_for_test_run(
#     test_run: TestRun,
#     test_runs_collection: Collection,
#     tracked_differences_collection: Collection,
#     changepoints_collection: Collection,
#     n_runs: int = 10,
# ) -> ControlGroup:
#     test_run_filters = {
#         "application": test_run.application,
#         "testType": test_run.testType,
#         "testEnvironment": test_run.testEnvironment,
#         "start": {"$lt": test_run.start},
#         "$or": [
#             {"consolidatedResult.meetsRequirement": True},
#             {"adaptMode": "BASELINE"},
#         ],
#     }
#
#     changepoint = find_most_recent_changepoint(
#         test_run=test_run,
#         test_runs_collection=test_runs_collection,
#         changepoints_collection=changepoints_collection,
#     )
#     if changepoint is not None:
#         changepoint_datetime = get_datetime_from_changepoint(
#             changepoint, test_runs_collection
#         )
#         test_run_filters["start"]["$gte"] = changepoint_datetime
#
#     control_runs = []
#     for test_run_doc in test_runs_collection.find(test_run_filters):
#         test_run_id = test_run_doc["testRunId"]
#         denied_diffs = tracked_differences_collection.find_one(
#             {"testRunId": test_run_id, "status": "DENIED"}
#         )
#         select_run = True if denied_diffs is None else False
#
#         if select_run is True:
#             control_runs.append(TestRun.model_validate(test_run_doc))
#
#         if len(control_runs) == n_runs:
#             break
#
#     n_test_runs = len(control_runs)
#     selected_run_ids = [x.testRunId for x in control_runs]
#     control_group = ControlGroup(
#         control_group_id=test_run.testRunId,
#         application=test_run.application,
#         test_type=test_run.testType,
#         test_environment=test_run.testEnvironment,
#         test_runs=selected_run_ids,
#         n_test_runs=len(selected_run_ids),
#         last_datetime=max([x.start for x in control_runs]) if n_test_runs > 0 else None,
#         first_datetime=min([x.start for x in control_runs])
#         if n_test_runs > 0
#         else None,
#     )
#     return control_group
#
#
# def get_datetime_from_changepoint(
#     changepoint: Changepoint, test_runs_collection: Collection
# ) -> datetime:
#     test_run_start = test_runs_collection.find_one(
#         {"testRunId": changepoint.test_run_id}, projection={"start": 1}
#     )["start"]
#     return test_run_start
