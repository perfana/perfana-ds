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
from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.pipelines.common import value_or_fill_aggregation

logger = get_task_logger(__name__)


def aggregate_adapt_input(test_run_ids: list[str]):
    logger.info(f"Calculate ADAPT input for {len(test_run_ids)} test runs")
    start_time = time()

    catalog = get_catalog()
    metric_statistics_dataset = catalog.ds.metricStatistics
    control_group_statistics_dataset = catalog.ds.controlGroupStatistics
    adapt_input_dataset = catalog.ds.adaptInput

    # Get test run info for compare config lookup
    test_run = catalog.testRuns.load_object({"testRunId": test_run_ids[0]})
    if test_run is None:
        raise FileNotFoundError(f"No test run found for id {test_run_ids[0]}")

    filter_pipe = [
        {"$match": {"testRunId": {"$in": test_run_ids}}},
        {
            "$addFields": {"controlGroupId": "$testRunId"}
        },  # assumes testRunId equals corresponding controlGroupId
    ]
    statistics_aggregation_pipe = _statistics_differences_pipeline(
        control_group_statistics_dataset, test_run
    )

    output_pipe = [
        {
            "$merge": {
                "into": adapt_input_dataset.collection_name,
                "on": [
                    "testRunId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]
    aggregation_pipeline = filter_pipe + statistics_aggregation_pipe + output_pipe

    _ = metric_statistics_dataset.collection.aggregate(aggregation_pipeline)

    output_counts = adapt_input_dataset.collection.count_documents(
        {"testRunId": {"$in": test_run_ids}}
    )
    logger.info(
        f"Finished statistics differences for {output_counts} metrics in {(time() - start_time):.2f} seconds"
    )

    # Collect metrics that used default values for backfilling
    metrics_using_defaults = list(
        adapt_input_dataset.collection.find(
            {"testRunId": {"$in": test_run_ids}, "_usesDefaultValue": True},
            {
                "applicationDashboardId": 1,
                "panelId": 1,
                "metricName": 1,
                "dashboardUid": 1,
                "dashboardLabel": 1,
                "panelTitle": 1,
                "unit": 1,
                "_defaultValue": 1,
            },
        )
    )

    if metrics_using_defaults:
        # Format metrics for backfill function
        formatted_metrics = []
        for metric in metrics_using_defaults:
            # Safety check: skip metrics without a valid default value
            default_value = metric.get("_defaultValue")
            if default_value is None:
                logger.warning(
                    f"Skipping metric {metric.get('metricName')} - missing default value"
                )
                continue

            formatted_metrics.append(
                {
                    "applicationDashboardId": metric["applicationDashboardId"],
                    "panelId": metric["panelId"],
                    "metricName": metric["metricName"],
                    "defaultValue": default_value,
                    "dashboardUid": metric.get("dashboardUid"),
                    "dashboardLabel": metric.get("dashboardLabel"),
                    "panelTitle": metric.get("panelTitle"),
                    "unit": metric.get("unit"),
                }
            )

        logger.info(
            f"Found {len(formatted_metrics)} metrics using default values - will trigger backfill"
        )

        # Clean up temporary fields
        adapt_input_dataset.collection.update_many(
            {"testRunId": {"$in": test_run_ids}},
            {"$unset": {"_usesDefaultValue": "", "_defaultValue": ""}},
        )

        return formatted_metrics

    return True


def _create_diff_aggregation(field_name: str):
    return {
        field_name: {
            "test": f"${field_name}",
            "control": {
                "$cond": [
                    {"$eq": [{"$type": f"$control.{field_name}"}, "missing"]},
                    # If control group data is missing, check for default value
                    {
                        "$cond": [
                            {
                                "$ne": [
                                    "$compareConfig.defaultValueIfControlGroupMissing.value",
                                    None,
                                ]
                            },
                            "$compareConfig.defaultValueIfControlGroupMissing.value",
                            None,
                        ]
                    },
                    f"$control.{field_name}",
                ]
            },
            "diff": {
                "$cond": [
                    {"$eq": [{"$type": f"$control.{field_name}"}, "missing"]},
                    # If control group data is missing, calculate diff using default value if available
                    {
                        "$cond": [
                            {
                                "$ne": [
                                    "$compareConfig.defaultValueIfControlGroupMissing.value",
                                    None,
                                ]
                            },
                            {
                                "$subtract": [
                                    f"${field_name}",
                                    "$compareConfig.defaultValueIfControlGroupMissing.value",
                                ]
                            },
                            None,
                        ]
                    },
                    {"$subtract": [f"${field_name}", f"$control.{field_name}"]},
                ]
            },
        }
    }


def _create_secondary_diff_aggregation(field_name: str):
    return {
        field_name: {
            "pctDiff": {
                "$cond": [
                    {"$eq": [f"${field_name}.control", 0]},
                    None,
                    {"$divide": [f"${field_name}.diff", f"${field_name}.control"]},
                ]
            },
            "absDiff": {"$abs": f"${field_name}.diff"},
        }
    }


def _create_iqr_diff_aggregation(field_name: str):
    return {
        field_name: {
            "iqrDiff": {
                "$cond": [
                    {"$eq": ["$iqr.control", 0]},
                    None,
                    {"$divide": [f"${field_name}.diff", "$iqr.control"]},
                ]
            },
        }
    }


def _statistics_differences_pipeline(
    control_group_statistics_dataset: MongoData,
    test_run,  # TestRun object
) -> list[dict[str, Any]]:
    primary_aggregations = {
        "exists": {
            "test": True,
            "control": {
                "$or": [
                    {"$gt": [{"$size": "$control_list"}, 0]},
                    # Only consider it as existing if we have a non-null default value configured
                    {
                        "$and": [
                            {
                                "$ne": [
                                    {
                                        "$type": "$compareConfig.defaultValueIfControlGroupMissing.value"
                                    },
                                    "missing",
                                ]
                            },
                            {
                                "$ne": [
                                    "$compareConfig.defaultValueIfControlGroupMissing.value",
                                    None,
                                ]
                            },
                        ]
                    },
                ]
            },
        },
        "isConstant": {
            "test": "$isConstant",
            "control": value_or_fill_aggregation("$control.isConstant"),
        },
        "allMissing": {
            "test": "$allMissing",
            "control": value_or_fill_aggregation("$control.allMissing"),
        },
    }

    secondary_aggregations = {}
    for field in [
        "mean",
        "median",
        "min",
        "max",
        "std",
        "iqr",
        "idr",
        "q10",
        "q25",
        "q75",
        "q90",
        "n",
        "nMissing",
        "pctMissing",
        "nNonZero",
    ]:
        primary_field_agg = _create_diff_aggregation(field_name=field)
        primary_aggregations.update(primary_field_agg)
        secondary_field_agg = _create_secondary_diff_aggregation(field_name=field)
        secondary_aggregations.update(secondary_field_agg)

    iqr_aggregations = {}
    for field in ["mean", "median", "min", "max"]:
        iqr_field_agg = _create_iqr_diff_aggregation(field_name=field)
        iqr_aggregations.update(iqr_field_agg)

    pipe = [
        {
            "$lookup": {
                "from": control_group_statistics_dataset.collection_name,
                "let": {
                    "controlGroupId": "$controlGroupId",
                    "applicationDashboardId": "$applicationDashboardId",
                    "panelId": "$panelId",
                    "metricName": "$metricName",
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$controlGroupId", "$$controlGroupId"]},
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
                    }
                ],
                "as": "control_list",
            }
        },
        # Lookup compare config to get default value configuration
        {
            "$lookup": {
                "from": "dsCompareConfig",
                "let": {
                    "application": test_run.application,
                    "testType": test_run.testType,
                    "testEnvironment": test_run.testEnvironment,
                    "applicationDashboardId": "$applicationDashboardId",
                    "panelId": "$panelId",
                    "panelTitle": "$panelTitle",
                    "metricName": "$metricName",
                },
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
                                            {"$eq": ["$panelTitle", "$$panelTitle"]},
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
                    {
                        "$sort": {
                            "defaultValueIfControlGroupMissing.source": -1,
                            "application": -1,
                            "testType": -1,
                            "testEnvironment": -1,
                            "applicationDashboardId": -1,
                            "panelTitle": -1,
                            "panelId": -1,
                            "metricName": -1,
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
                "as": "compareConfig_list",
            }
        },
        {"$addFields": {"control": {"$arrayElemAt": ["$control_list", 0]}}},
        {"$addFields": {"compareConfig": {"$arrayElemAt": ["$compareConfig_list", 0]}}},
        # Set default compareConfig if no match found, or add missing defaultValueIfControlGroupMissing field
        {
            "$addFields": {
                "compareConfig": {
                    "$cond": [
                        {"$eq": [{"$type": "$compareConfig"}, "missing"]},
                        # No compareConfig found - use default
                        {
                            "defaultValueIfControlGroupMissing": {
                                "value": None,
                                "source": "default",
                            }
                        },
                        # compareConfig found - ensure it has defaultValueIfControlGroupMissing field
                        {
                            "$mergeObjects": [
                                "$compareConfig",
                                {
                                    "defaultValueIfControlGroupMissing": {
                                        "$ifNull": [
                                            "$compareConfig.defaultValueIfControlGroupMissing",
                                            {"value": None, "source": "default"},
                                        ]
                                    }
                                },
                            ]
                        },
                    ]
                }
            }
        },
        {"$addFields": primary_aggregations},
        {"$addFields": secondary_aggregations},
        {"$addFields": iqr_aggregations},
        # Add field to track if default values are being used (for backfill feature)
        {
            "$addFields": {
                "_usesDefaultValue": {
                    "$and": [
                        {
                            "$eq": [{"$size": "$control_list"}, 0]
                        },  # No control group data
                        {
                            "$ne": [
                                "$compareConfig.defaultValueIfControlGroupMissing.value",
                                None,
                            ]
                        },  # Has default value
                    ]
                },
                # Store the default value so we can access it later (since compareConfig will be removed)
                "_defaultValue": {
                    "$ifNull": [
                        "$compareConfig.defaultValueIfControlGroupMissing.value",
                        None,
                    ]
                },
            }
        },
        # Select only fields we want as output
        {
            "$project": {
                "_id": 0,
                "control": 0,
                "control_list": 0,
                "compareConfig": 0,
                "compareConfig_list": 0,
            }
        },
    ]
    return pipe
