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
from typing import Any

from celery.utils.log import get_task_logger

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.pipelines.common import value_or_fill_aggregation
from perfana_ds.schemas.compare_config import CompareConfigDocument
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def aggregate_adapt_results(test_run_ids: list[str]) -> bool:
    catalog = get_catalog()
    adapt_input_dataset = catalog.ds.adaptInput
    adapt_results_dataset = catalog.ds.adaptResults

    test_run_ids = list(set(test_run_ids))
    if len(test_run_ids) == 0:
        raise ValueError("No test runs passed to function.")

    logger.info(f"Aggregating ADAPT results for {len(test_run_ids)} test runs")
    start_time = time()
    filter_pipeline = [{"$match": {"testRunId": {"$in": test_run_ids}}}]

    # require 1 test run object to build adapt result pipeline
    catalog = get_catalog()
    test_run = catalog.testRuns.load_object({"testRunId": test_run_ids[0]})
    if test_run is None:
        raise FileNotFoundError(f"No test run found for id {test_run_ids[0]}")

    adapt_pipeline = _adapt_result_pipeline(test_run)
    output_pipeline = [
        {
            "$merge": {
                "into": adapt_results_dataset.collection_name,
                "on": adapt_results_dataset.upsert_fields,
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]
    pipeline = filter_pipeline + adapt_pipeline + output_pipeline
    # print("aggregate_adapt_results: " + str(pipeline))

    _ = adapt_input_dataset.collection.aggregate(pipeline)

    output_counts = adapt_results_dataset.collection.count_documents(
        {"testRunId": {"$in": test_run_ids}}
    )
    logger.info(
        f"Finished ADAPT results for {output_counts} metrics in {(time() - start_time):.2f} seconds"
    )
    return True


def _get_default_compare_config():
    compare_config = CompareConfigDocument(id="default")
    default_compare_config = compare_config.model_dump(by_alias=True)
    return default_compare_config


def _adapt_result_pipeline(test_run: TestRun) -> list[dict[str, Any]]:
    default_compare_config = _get_default_compare_config()
    pipeline = [
        # Lookup compare config thresholds from collection on 6 fields of increasing detail
        {
            "$lookup": {
                "from": "dsCompareConfig",
                "let": {
                    "application": test_run.application,
                    "testType": test_run.testType,
                    "testEnvironment": test_run.testEnvironment,
                    "applicationDashboardId": "$applicationDashboardId",
                    "panelId": "$panelId",
                    "metricName": "$metricName",
                },
                # Match on all possible join fields, and sort so that null fields are last
                # then select first match, which will be the one that matches on most fields
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {
                                        "$or": [
                                            {"$eq": ["$application", "$$application"]},
                                            {"$eq": ["$application", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$testType", "$$testType"]},
                                            {"$eq": ["$testType", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    "$testEnvironment",
                                                    "$$testEnvironment",
                                                ]
                                            },
                                            {"$eq": ["$testEnvironment", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    "$applicationDashboardId",
                                                    "$$applicationDashboardId",
                                                ]
                                            },
                                            {"$eq": ["$applicationDashboardId", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$panelId", "$$panelId"]},
                                            {"$eq": ["$panelId", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$metricName", "$$metricName"]},
                                            {"$eq": ["$metricName", None]},
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    # Sort so that null values for each field are last
                    {
                        "$sort": {
                            "ignore.source": -1,
                            "statistic.source": -1,
                            "iqrThreshold.source": -1,
                            "pctThreshold.source": -1,
                            "absThreshold.source": -1,
                            "nThreshold.source": -1,
                        }
                    },
                    {
                        "$project": {
                            "application": 0,
                            "testType": 0,
                            "testEnvironment": 0,
                            "applicationDashboardId": 0,
                            "dashboardLabel": 0,
                            "dashboardUid": 0,
                            "panelId": 0,
                            "panelTitle": 0,
                            "metricName": 0,
                            "regex": 0,
                        }
                    },
                ],
                "as": "compareConfig",
            }
        },
        # Find matching metric classification
        {
            "$lookup": {
                "from": "metricClassification",
                "let": {
                    "application": test_run.application,
                    "testType": test_run.testType,
                    "testEnvironment": test_run.testEnvironment,
                    "applicationDashboardId": "$applicationDashboardId",
                    "panelId": "$panelId",
                    "metricName": "$metricName",
                },
                # Match on all possible join fields, and sort so that null fields are last
                # then select first match, which will be the one that matches on most fields
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {
                                        "$or": [
                                            {"$eq": ["$application", "$$application"]},
                                            {"$eq": ["$application", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$testType", "$$testType"]},
                                            {"$eq": ["$testType", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    "$testEnvironment",
                                                    "$$testEnvironment",
                                                ]
                                            },
                                            {"$eq": ["$testEnvironment", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    "$applicationDashboardId",
                                                    "$$applicationDashboardId",
                                                ]
                                            },
                                            {"$eq": ["$applicationDashboardId", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$panelId", "$$panelId"]},
                                            {"$eq": ["$panelId", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$metricName", "$$metricName"]},
                                            {"$eq": ["$metricName", None]},
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    # Sort so that null values for each field are last
                    {
                        "$sort": {
                            "application": -1,
                            "testType": -1,
                            "testEnvironment": -1,
                            "applicationDashboardId": -1,
                            "panelId": -1,
                            "metricName": -1,
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "metricClassification": 1,
                            "higherIsBetter": 1,
                        }
                    },
                ],
                "as": "metricClassification",
            }
        },
        # Select only the first match, containing the most detailed matching config
        {
            "$addFields": {
                "compareConfig": {"$first": "$compareConfig"},
                "metricClassification": {"$first": "$metricClassification"},
            }
        },
        # If no matches are found at all, use a built-in default compare config
        {
            "$fill": {
                "output": {
                    "compareConfig": {"value": default_compare_config},
                    "metricClassification": {
                        "value": {
                            "_id": None,
                            "metricClassification": None,
                            "higherIsBetter": None,
                        }
                    },
                }
            }
        },
        # Select statistic to test
        ## Create key-value pair of document
        ## For each document, select they field according to compare config
        ## Keep only the matching field and then drop the key-value object
        {
            "$addFields": {
                "_data": {
                    "$first": {
                        "$filter": {
                            "input": {"$objectToArray": "$$ROOT"},
                            "as": "pair",
                            "cond": {
                                "$eq": ["$$pair.k", "$compareConfig.statistic.value"]
                            },
                        }
                    }
                }
            }
        },
        {"$addFields": {"statistic": "$_data.v"}},
        {"$addFields": {"statistic": {"name": "$_data.k"}}},
        {"$project": {"_data": 0}},
        # Add fields for comparison conditions
        {
            "$addFields": {
                "conditions": {
                    "enoughObservations": {
                        "$gt": ["$n.test", "$compareConfig.nThreshold.value"]
                    },
                    "notAllMissing": {"$not": "$allMissing.test"},
                    "controlNotConstant": {"$not": "$isConstant.control"},
                    "controlConstant": "$isConstant.control",
                    "controlNotZero": {"$ne": ["$statistic.value", 0]},
                    "controlExists": "$exists.control",
                    "hasAbsCheck": {"$ne": ["$compareConfig.absThreshold.value", None]},
                    "iqrNotZero": {"$gt": ["$iqr.control", 0]},
                },
                "thresholds": {
                    "upper": {
                        "pct": {
                            "$multiply": [
                                "$statistic.control",
                                {"$add": [1, "$compareConfig.pctThreshold.value"]},
                            ]
                        },
                        "iqr": {
                            "$add": [
                                "$statistic.control",
                                {
                                    "$multiply": [
                                        "$iqr.control",
                                        "$compareConfig.iqrThreshold.value",
                                    ]
                                },
                            ]
                        },
                        "abs": {
                            "$add": [
                                "$statistic.control",
                                {"$toDouble": "$compareConfig.absThreshold.value"},
                            ]
                        },
                        "constant": {"$ifNull": ["$statistic.control", 0]},
                    },
                    "lower": {
                        "pct": {
                            "$multiply": [
                                "$statistic.control",
                                {"$subtract": [1, "$compareConfig.pctThreshold.value"]},
                            ]
                        },
                        "iqr": {
                            "$subtract": [
                                "$statistic.control",
                                {
                                    "$multiply": [
                                        "$iqr.control",
                                        "$compareConfig.iqrThreshold.value",
                                    ]
                                },
                            ]
                        },
                        "abs": {
                            "$subtract": [
                                "$statistic.control",
                                {"$toDouble": "$compareConfig.absThreshold.value"},
                            ]
                        },
                        "constant": {"$ifNull": ["$statistic.control", 0]},
                    },
                },
            }
        },
        # Add fields that depend on calculated fields above
        {
            "$addFields": {
                "thresholds": {
                    "upper": {
                        "$mergeObjects": [
                            "$thresholds.upper",
                            {
                                "overall": {
                                    "$max": [
                                        "$thresholds.upper.pct",
                                        "$thresholds.upper.iqr",
                                        "$thresholds.upper.abs",
                                    ]
                                }
                            },
                        ]
                    },
                    "lower": {
                        "$mergeObjects": [
                            "$thresholds.lower",
                            {
                                "overall": {
                                    "$min": [
                                        "$thresholds.lower.pct",
                                        "$thresholds.lower.iqr",
                                        "$thresholds.lower.abs",
                                    ]
                                }
                            },
                        ]
                    },
                }
            }
        },
        # Add fields to signifiy increase/decrease according to thresholds
        {
            "$addFields": {
                "checks": {
                    "pct": {
                        "valid": {
                            "$and": [
                                "$conditions.enoughObservations",
                                "$conditions.controlExists",
                                "$conditions.notAllMissing",
                                "$conditions.controlNotZero",
                            ]
                        },
                        "increase": {
                            "$gt": ["$statistic.test", "$thresholds.upper.pct"]
                        },
                        "decrease": {
                            "$lt": ["$statistic.test", "$thresholds.upper.pct"]
                        },
                        "observedDiff": value_or_fill_aggregation("$statistic.pctDiff"),
                        "isDifference": {
                            "$or": [
                                {"$gt": ["$statistic.test", "$thresholds.upper.pct"]},
                                {"$lt": ["$statistic.test", "$thresholds.lower.pct"]},
                            ]
                        },
                        "invalidReasons": ["TODO"],
                    },
                    "iqr": {
                        "valid": {
                            "$and": [
                                "$conditions.enoughObservations",
                                "$conditions.controlExists",
                                "$conditions.notAllMissing",
                                "$conditions.controlNotZero",
                            ]
                        },
                        "observedDiff": value_or_fill_aggregation("$statistic.iqrDiff"),
                        "increase": {
                            "$gt": ["$statistic.test", "$thresholds.upper.iqr"]
                        },
                        "decrease": {
                            "$lt": ["$statistic.test", "$thresholds.lower.iqr"]
                        },
                        "isDifference": {
                            "$or": [
                                {"$gt": ["$statistic.test", "$thresholds.upper.iqr"]},
                                {"$lt": ["$statistic.test", "$thresholds.lower.iqr"]},
                            ]
                        },
                        "invalidReasons": ["TODO"],
                    },
                    "abs": {
                        "valid": {
                            "$and": [
                                "$conditions.enoughObservations",
                                "$conditions.controlExists",
                                "$conditions.notAllMissing",
                                "$conditions.hasAbsCheck",
                            ]
                        },
                        "increase": {
                            "$gt": ["$statistic.test", "$thresholds.upper.abs"]
                        },
                        "decrease": {
                            "$lt": ["$statistic.test", "$thresholds.lower.abs"]
                        },
                        "observedDiff": value_or_fill_aggregation("$statistic.absDiff"),
                        "isDifference": {
                            "$or": [
                                {"$gt": ["$statistic.test", "$thresholds.upper.abs"]},
                                {"$lt": ["$statistic.test", "$thresholds.lower.abs"]},
                            ]
                        },
                        "invalidReasons": ["TODO"],
                    },
                    "constant": {
                        "valid": {
                            "$and": [
                                "$conditions.enoughObservations",
                                "$conditions.controlExists",
                                "$conditions.controlConstant",
                            ]
                        },
                        "increase": {
                            "$gt": ["$statistic.test", "$thresholds.upper.constant"]
                        },
                        "decrease": {
                            "$lt": ["$statistic.test", "$thresholds.lower.constant"]
                        },
                        "observedDiff": value_or_fill_aggregation("$statistic.diff"),
                        "isDifference": {
                            "$or": [
                                {
                                    "$gt": [
                                        "$statistic.test",
                                        "$thresholds.upper.constant",
                                    ]
                                },
                                {
                                    "$lt": [
                                        "$statistic.test",
                                        "$thresholds.lower.constant",
                                    ]
                                },
                            ]
                        },
                        "invalidReasons": ["TODO"],
                    },
                }
            }
        },
        # Add Conclusion field based on check results
        {
            "$addFields": {
                "conclusion": {
                    "valid": {
                        "$or": [
                            "$checks.pct.valid",
                            "$checks.abs.valid",
                            "$checks.iqr.valid",
                            "$checks.constant.valid",
                        ]
                    },
                    "partialDifference": {
                        "$or": [
                            {"$and": ["$checks.pct.isDifference", "$checks.pct.valid"]},
                            {"$and": ["$checks.abs.isDifference", "$checks.abs.valid"]},
                            {"$and": ["$checks.iqr.isDifference", "$checks.iqr.valid"]},
                            {
                                "$and": [
                                    "$checks.constant.isDifference",
                                    "$checks.constant.valid",
                                ]
                            },
                        ]
                    },
                    "allDifference": {
                        "$and": [
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            "$checks.pct.isDifference",
                                            "$checks.pct.valid",
                                        ]
                                    },
                                    {"$not": "$checks.pct.valid"},
                                ]
                            },
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            "$checks.abs.isDifference",
                                            "$checks.abs.valid",
                                        ]
                                    },
                                    {"$not": "$checks.abs.valid"},
                                ]
                            },
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            "$checks.iqr.isDifference",
                                            "$checks.iqr.valid",
                                        ]
                                    },
                                    {"$not": "$checks.iqr.valid"},
                                ]
                            },
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            "$checks.constant.isDifference",
                                            "$checks.constant.valid",
                                        ]
                                    },
                                    {"$not": "$checks.constant.valid"},
                                ]
                            },
                            {
                                "$or": [
                                    "$checks.pct.valid",
                                    "$checks.abs.valid",
                                    "$checks.iqr.valid",
                                    "$checks.constant.valid",
                                ]
                            },
                            # at least one valid check
                        ]
                    },
                    "increase": {"$gt": ["$statistic.diff", 0]},
                    "decrease": {"$lt": ["$statistic.diff", 0]},
                    "ignore": "$compareConfig.ignore.value",
                }
            }
        },
        {
            "$addFields": {
                "conclusion": {
                    "label": {
                        "$cond": [
                            "$conclusion.allDifference",
                            # if all valid checks find differences
                            {
                                "$cond": [
                                    {
                                        "$eq": [
                                            "$metricClassification.higherIsBetter",
                                            None,
                                        ]
                                    },  # condition
                                    {
                                        "$cond": [
                                            "$conclusion.increase",
                                            "increase",
                                            "decrease",
                                        ]
                                    },
                                    # if higherIsBetter is None
                                    {
                                        "$cond": [  # if higherIsBetter is True/False
                                            "$metricClassification.higherIsBetter",
                                            {
                                                "$cond": [
                                                    "$conclusion.increase",
                                                    "improvement",
                                                    "regression",
                                                ]
                                            },
                                            # if higherIsBetter is True
                                            {
                                                "$cond": [
                                                    "$conclusion.increase",
                                                    "regression",
                                                    "improvement",
                                                ]
                                            },
                                            # if higherIsBetter is False
                                        ]
                                    },
                                ]
                            },
                            {
                                "$cond": [
                                    "$conclusion.partialDifference",
                                    # if there is a difference on a check, but not on all checks
                                    {
                                        "$cond": [
                                            {
                                                "$eq": [
                                                    "$metricClassification.higherIsBetter",
                                                    None,
                                                ]
                                            },  # condition
                                            {
                                                "$cond": [
                                                    "$conclusion.increase",
                                                    "partial increase",
                                                    "partial decrease",
                                                ]
                                            },
                                            # if higherIsBetter is None
                                            {
                                                "$cond": [  # if higherIsBetter is True/False
                                                    "$metricClassification.higherIsBetter",
                                                    {
                                                        "$cond": [
                                                            "$conclusion.increase",
                                                            "partial improvement",
                                                            "partial regression",
                                                        ]
                                                    },  # if higherIsBetter is True
                                                    {
                                                        "$cond": [
                                                            "$conclusion.increase",
                                                            "partial regression",
                                                            "partial improvement",
                                                        ]
                                                    },  # if higherIsBetter is False
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        "$cond": [
                                            "$conclusion.valid",
                                            "no difference",
                                            "incomparable",
                                        ]
                                    },
                                ]
                            },
                        ]
                    }
                }
            }
        },
    ]

    return pipeline
