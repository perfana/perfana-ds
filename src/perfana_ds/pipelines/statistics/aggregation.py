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
from typing import Any

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.pipelines.common import value_or_fill_aggregation
from perfana_ds.schemas.control_groups import ControlGroup


def aggregate_metric_statistics(
    test_run_ids: list[str],
    extra_fields: dict[str, Any] | None = None,
) -> bool:
    catalog = get_catalog()
    panels_dataset = catalog.ds.panels
    metrics_dataset = catalog.ds.metrics
    statistics_dataset = catalog.ds.metricStatistics
    test_runs_dataset = catalog.testRuns

    if extra_fields is None:
        extra_fields = {}

    group_id = {
        "testRunId": "$testRunId",
        "applicationDashboardId": "$applicationDashboardId",
        "panelId": "$panelId",
        "metricName": "$data.metricName",
    }
    filter_stage = [{"$match": {"testRunId": {"$in": test_run_ids}}}]
    aggregation_stage = _aggregate_statistics_stage(group_id, extra_fields=extra_fields)
    panel_info_pipe = _lookup_panel_info_stage(panels_dataset)

    output_pipe = [
        {
            "$merge": {
                "into": statistics_dataset.collection_name,
                "on": statistics_dataset.upsert_fields,
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]

    test_run_info_pipe = _lookup_test_run_info_stage(test_runs_dataset)
    pipeline = (
        filter_stage
        + aggregation_stage
        + panel_info_pipe
        + test_run_info_pipe
        + output_pipe
    )
    # print("aggregate_metric_statistics: " + str(pipeline))

    _ = metrics_dataset.collection.aggregate(pipeline)
    return True


def aggregate_control_group_statistics(
    control_groups: list[ControlGroup],
    extra_fields: dict[str, Any] | None = None,
):
    catalog = get_catalog()
    panels_dataset = catalog.ds.panels
    control_groups_dataset = catalog.ds.controlGroup
    output_dataset = catalog.ds.controlGroupStatistics

    if extra_fields is None:
        extra_fields = {}

    extra_fields = extra_fields | {
        "testRunId": "$controlGroupId"
    }  # required for panel info lookup
    group_id = {
        "controlGroupId": "$controlGroupId",
        "applicationDashboardId": "$applicationDashboardId",
        "panelId": "$panelId",
        "metricName": "$data.metricName",
    }

    control_groups = deduplicate_control_groups(control_groups)
    filter_stage = _select_control_group_metrics_stage(control_groups)
    aggregation_stage = _aggregate_statistics_stage(group_id, extra_fields=extra_fields)
    panel_info_pipe = _lookup_panel_info_stage(panels_dataset)

    output_pipe = [
        {
            "$merge": {
                "into": output_dataset.collection_name,
                "on": output_dataset.upsert_fields,
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        }
    ]

    pipeline = filter_stage + aggregation_stage + panel_info_pipe + output_pipe
    # print("aggregate_control_group_statistics: " + str(pipeline))
    _ = control_groups_dataset.collection.aggregate(pipeline)
    return True


def _lookup_panel_info_stage(panels_dataset: MongoData) -> list[dict[str, Any]]:
    pipe = [
        {
            "$lookup": {
                "from": panels_dataset.collection_name,
                "let": {
                    "applicationDashboardId": "$applicationDashboardId",
                    "panelId": "$panelId",
                    "testRunId": "$testRunId",
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
                                ]
                            }
                        }
                    }
                ],
                "as": "panel",
            }
        },
        {"$addFields": {"panel": {"$first": "$panel"}}},
        {
            "$addFields": {
                "dashboardUid": value_or_fill_aggregation(
                    "$panel.dashboardUid", "missing"
                ),
                "dashboardLabel": value_or_fill_aggregation(
                    "$panel.dashboardLabel", "missing"
                ),
                "panelTitle": value_or_fill_aggregation("$panel.panelTitle", "missing"),
                "unit": "$panel.panel.fieldConfig.defaults.unit",
                "benchmarkIds": "$panel.benchmarkIds",
            }
        },
        {"$fill": {"output": {"unit": {"value": None}}}},
        {"$project": {"panel": 0}},
    ]
    return pipe


def _lookup_test_run_info_stage(test_runs_dataset: MongoData) -> list[dict[str, Any]]:
    pipe = [
        {
            "$lookup": {
                "from": test_runs_dataset.collection_name,
                "localField": "testRunId",
                "foreignField": "testRunId",
                "as": "test_run",
            }
        },
        {"$addFields": {"testRunStart": {"$first": "$test_run.start"}}},
        {"$project": {"test_run": 0}},
    ]
    return pipe


def _aggregate_statistics_stage(
    group_id: dict[str, str], extra_fields: dict[str, Any] = None
) -> list[dict[str, Any]]:
    if extra_fields is None:
        extra_fields = {}

    return [
        # Unwind each record in the $data list to a new doc
        {"$unwind": "$data"},
        # Exclude rampup values
        {"$match": {"data.rampUp": False}},
        # Aggregate statistics by group
        {
            "$group": {
                "_id": group_id,
                "mean": {"$avg": "$data.value"},
                "min": {"$min": "$data.value"},
                "max": {"$max": "$data.value"},
                "std": {"$stdDevPop": "$data.value"},
                "last": {"$last": "$data.value"},
                "n": {"$count": {}},
                "nMissing": {
                    "$sum": {
                        "$cond": [
                            {"$ifNull": ["$data.value", False]},
                            0,
                            1,
                        ]  # Condition for counting missing values
                    }
                },
                "nNonZero": {
                    "$sum": {
                        "$cond": [
                            {"$gt": ["$data.value", 0]},
                            1,
                            0,
                        ]  # Condition for counting nonzero values
                    }
                },
                "distinctValues": {"$addToSet": "$data.value"},
                "percentiles": {
                    "$percentile": {
                        "input": "$data.value",
                        "p": [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99],
                        "method": "approximate",
                    }
                },
            }
        },
        # Derive and unwind result statistics
        {
            "$addFields": {
                "q10": {"$arrayElemAt": ["$percentiles", 0]},
                "q25": {"$arrayElemAt": ["$percentiles", 1]},
                "median": {"$arrayElemAt": ["$percentiles", 2]},
                "q75": {"$arrayElemAt": ["$percentiles", 3]},
                "q90": {"$arrayElemAt": ["$percentiles", 4]},
                "q95": {"$arrayElemAt": ["$percentiles", 5]},
                "q99": {"$arrayElemAt": ["$percentiles", 6]},
                "isConstant": {"$eq": [{"$size": "$distinctValues"}, 1]},
                "allMissing": {"$eq": ["$n", "$nMissing"]},
                "pctMissing": {"$divide": ["$nMissing", "$n"]},
                "updatedAt": datetime.utcnow(),
            }
        },
        # Derive additional fields that depend on fields above
        {
            "$addFields": {
                "iqr": {"$subtract": ["$q75", "$q25"]},
                "idr": {"$subtract": ["$q90", "$q10"]},
            }
        },
        {"$addFields": {key: f"$_id.{key}" for key in group_id.keys()}},
        # Add additional fields from parameter input
        {"$addFields": extra_fields},
        # Drop intermediate fields we do not need
        {"$project": {"_id": 0, "percentiles": 0, "distinctValues": 0}},
        # Merge output into target collection
    ]


def deduplicate_control_groups(
    control_groups: list[ControlGroup],
) -> list[ControlGroup]:
    control_group_ids = []
    control_group_indexes = []
    for i, control_group in enumerate(control_groups):
        if control_group.control_group_id not in control_group_ids:
            control_group_ids.append(control_group.control_group_id)
            control_group_indexes.append(i)
    return [control_groups[i] for i in control_group_indexes]


def _select_control_group_metrics_stage(control_groups: list[ControlGroup]):
    """Select dsMetrics for test runs of multiple control groups, using $facet stage."""
    control_groups = deduplicate_control_groups(control_groups)
    control_group_ids = [cg.control_group_id for cg in control_groups]
    return [
        {"$match": {"controlGroupId": {"$in": control_group_ids}}},
        {"$project": {"testRuns": 1, "controlGroupId": 1}},
        {"$unwind": "$testRuns"},
        {
            "$lookup": {
                "from": "dsMetrics",
                "localField": "testRuns",
                "foreignField": "testRunId",
                "as": "metrics",
            }
        },
        {"$unwind": "$metrics"},
        {"$addFields": {"metrics": {"controlGroupId": "$controlGroupId"}}},
        {"$replaceRoot": {"newRoot": "$metrics"}},
    ]
