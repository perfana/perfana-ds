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

logger = get_task_logger(__name__)


def aggregate_adapt_conclusion(test_run_ids: list[str]):
    logger.info(f"Creating ADAPT conclusion for {len(test_run_ids)} test runs")
    start_time = time()
    catalog = get_catalog()
    adapt_results_dataset = catalog.ds.adaptResults
    adapt_tracked_results_dataset = catalog.ds.adaptTrackedResults
    adapt_conclusion_dataset = catalog.ds.adaptConclusion

    _ = adapt_results_dataset.collection.aggregate(
        [
            {
                "$match": {
                    "testRunId": {"$in": test_run_ids},
                    "conclusion.ignore": False,
                }
            },
            {
                "$group": {
                    "_id": {
                        "testRunId": "$testRunId",
                        "controlGroupId": "$controlGroupId",
                    },
                    "regressions": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$conclusion.label", "regression"]},
                                "$_id",
                                "$$REMOVE",
                            ]
                        }
                    },
                    "improvements": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$conclusion.label", "improvement"]},
                                "$_id",
                                "$$REMOVE",
                            ]
                        }
                    },
                    "differences": {
                        "$push": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$conclusion.label",
                                        [
                                            "partial increase",
                                            "partial decrease",
                                            "increase",
                                            "decrease",
                                        ],
                                    ]
                                },
                                "$_id",
                                "$$REMOVE",
                            ]
                        }
                    },
                    "noDifferences": {
                        "$push": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$conclusion.label",
                                        ["no difference"],
                                    ]
                                },
                                "$_id",
                                "$$REMOVE",
                            ]
                        }
                    },
                    "incomparable": {
                        "$push": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$conclusion.label",
                                        ["incomparable"],
                                    ]
                                },
                                "$_id",
                                "$$REMOVE",
                            ]
                        }
                    },
                }
            },
            {
                "$lookup": {
                    "from": adapt_tracked_results_dataset.collection_name,
                    "localField": "_id.testRunId",
                    "foreignField": "testRunId",
                    "as": "trackedResults",
                }
            },
            {
                "$addFields": {
                    "trackedRegressions": {
                        "$filter": {
                            "input": "$trackedResults",
                            "as": "x",
                            "cond": {
                                "$and": [
                                    {"$eq": ["$$x.conclusion.label", "regression"]},
                                    {"$eq": ["$$x.conclusion.ignore", False]},
                                ]
                            },
                        }
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "testRunId": "$_id.testRunId",
                    "controlGroupId": "$_id.controlGroupId",
                    "regressions": 1,
                    "improvements": 1,
                    "differences": 1,
                    "trackedRegressions": "$trackedRegressions._id",
                    "conclusion": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": [{"$size": "$regressions"}, 0]},
                                    {"$eq": [{"$size": "$improvements"}, 0]},
                                    {"$eq": [{"$size": "$differences"}, 0]},
                                    {"$eq": [{"$size": "$trackedRegressions"}, 0]},
                                    {"$eq": [{"$size": "$noDifferences"}, 0]},
                                    {"$eq": [{"$size": "$incomparable"}, 0]},
                                ]
                            },
                            "SKIPPED",
                            {
                                "$cond": [
                                    {
                                        "$or": [
                                            {"$gt": [{"$size": "$regressions"}, 0]},
                                            {
                                                "$gt": [
                                                    {"$size": "$trackedRegressions"},
                                                    0,
                                                ]
                                            },
                                        ]
                                    },
                                    "REGRESSION",
                                    "PASSED",
                                ]
                            },
                        ]
                    },
                    "details": {
                        "message": {
                            "$cond": [
                                {"$gt": [{"$size": "$regressions"}, 0]},
                                "New regressions detected",
                                {
                                    "$cond": [
                                        {"$gt": [{"$size": "$trackedRegressions"}, 0]},
                                        "Only tracked regressions detected",
                                        "No regressions detected",
                                    ]
                                },
                            ]
                        }
                    },
                    "updatedAt": "$$NOW",
                }
            },
            {
                "$merge": {
                    "into": adapt_conclusion_dataset.collection_name,
                    "on": adapt_conclusion_dataset.upsert_fields,
                    "whenMatched": "replace",
                    "whenNotMatched": "insert",
                }
            },
        ]
    )

    logger.info(f"Finished ADAPT conclusion in {(time() - start_time):.2f} seconds")
    return True
