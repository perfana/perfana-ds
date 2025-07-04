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

from celery.utils.log import get_task_logger
from pymongo import UpdateOne

from perfana_ds.catalog.catalog import Catalog
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def find_benchmarks_mapping(
    catalog: Catalog, test_run: TestRun
) -> list[dict[str, Any]]:
    """Aggregate benchmarks for a given test run, and join applicationDashboardId.

    Returns:
        A list of dictionaries with keys 'benchmarkIds', 'applicationDashboardId', 'panelId'.
    """
    cursor = catalog.benchmarks.collection.aggregate(
        [
            # Match benchmarks for test run
            {
                "$match": {
                    "application": test_run.application,
                    "testType": test_run.testType,
                    "testEnvironment": test_run.testEnvironment,
                }
            },
            # Lookup applicationDashboardId
            {
                "$lookup": {
                    "from": "applicationDashboards",
                    "let": {
                        "application": "$application",
                        "testEnvironment": "$testEnvironment",
                        "dashboardLabel": "$dashboardLabel",
                    },
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$application", "$$application"]},
                                        {
                                            "$eq": [
                                                "$dashboardLabel",
                                                "$$dashboardLabel",
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$testEnvironment",
                                                "$$testEnvironment",
                                            ]
                                        },
                                    ]
                                }
                            }
                        },
                    ],
                    "as": "application_dashboards",
                }
            },
            {
                "$group": {
                    "_id": {
                        "panelId": "$panel.id",
                        "applicationDashboardId": {
                            "$first": "$application_dashboards._id"
                        },
                    },
                    "benchmarkIds": {"$push": "$_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "panelId": "$_id.panelId",
                    "applicationDashboardId": "$_id.applicationDashboardId",
                    "benchmarkIds": 1,
                }
            },
        ]
    )
    result = list(cursor)
    return result


def find_missing_benchmark_metrics(
    catalog: Catalog, test_run_id: str, benchmarks_mapping: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Check the metrics collection and find if there are metrics with benchmarks that are missing."""
    if len(benchmarks_mapping) == 0:
        return []

    filters = [
        {
            "testRunId": test_run_id,
            "applicationDashboardId": benchmark["applicationDashboardId"],
            "panelId": benchmark["panelId"],
        }
        for benchmark in benchmarks_mapping
    ]

    cursor = catalog.ds.metrics.collection.find(
        {"$or": filters},
        projection={"_id": 1, "applicationDashboardId": 1, "panelId": 1},
    )
    result = list(cursor)

    missing_benchmarks_mapping = []
    if len(result) != len(benchmarks_mapping):
        for benchmark in benchmarks_mapping:
            for doc in result:
                if (
                    doc["applicationDashboardId"] == benchmark["applicationDashboardId"]
                ) and (doc["panelId"] == benchmark["panelId"]):
                    break
            else:
                missing_benchmarks_mapping.append(benchmark)
    return missing_benchmarks_mapping


def find_missing_benchmark_panels(
    catalog: Catalog, test_run_id: str, benchmarks_mapping: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Check the panels collection and find if there are panels with benchmarks that are missing."""
    if len(benchmarks_mapping) == 0:
        return []

    filters = [
        {
            "testRunId": test_run_id,
            "applicationDashboardId": benchmark["applicationDashboardId"],
            "panelId": benchmark["panelId"],
        }
        for benchmark in benchmarks_mapping
    ]

    cursor = catalog.ds.panels.collection.find(
        {"$or": filters},
        projection={"_id": 1, "applicationDashboardId": 1, "panelId": 1},
    )
    panel_docs = list(cursor)

    missing_benchmarks_mapping = []
    for benchmark in benchmarks_mapping:
        for panel_doc in panel_docs:
            if (
                panel_doc["applicationDashboardId"]
                == benchmark["applicationDashboardId"]
            ) and (panel_doc["panelId"] == benchmark["panelId"]):
                break
        else:
            missing_benchmarks_mapping.append(benchmark)
    return missing_benchmarks_mapping


def get_panels_for_missing_metrics(
    catalog: Catalog, test_run_id: str, missing_benchmarks_mapping: list[dict[str, Any]]
) -> list[PanelDocument]:
    """Query and parse Panel objects for missing metrics."""
    if len(missing_benchmarks_mapping) == 0:
        return []

    panel_filters = [
        {
            "testRunId": test_run_id,
            "applicationDashboardId": benchmark["applicationDashboardId"],
            "panelId": benchmark["panelId"],
        }
        for benchmark in missing_benchmarks_mapping
    ]
    panels = catalog.ds.panels.load_objects({"$or": panel_filters})
    return panels


def update_benchmark_ids_for_panels_and_metrics(
    catalog: Catalog, test_run_id: str, benchmarks_mapping: list[dict[str, Any]]
):
    logger.info(f"Updating {len(benchmarks_mapping)} benchmark ids for {test_run_id}")
    # build queries to update benchmarkIds in panels and metrics
    update_queries = [
        UpdateOne(
            {
                "testRunId": test_run_id,
                "applicationDashboardId": benchmarks_mapping["applicationDashboardId"],
                "panelId": benchmarks_mapping["panelId"],
            },
            update={
                "$set": {
                    "benchmarkIds": benchmarks_mapping["benchmarkIds"],
                    "updatedAt": datetime.now(),
                }
            },
            upsert=True,
        )
        for benchmarks_mapping in benchmarks_mapping
    ]

    # update panels collection
    catalog.ds.panels.collection.update_many(
        {"testRunId": test_run_id}, update={"$set": {"benchmarkIds": []}}, upsert=True
    )
    panels_result = catalog.ds.panels.collection.bulk_write(update_queries)
    logger.info(f"Updated panel benchmarkIds for {test_run_id}: {panels_result}")

    # update metrics collection
    catalog.ds.metrics.collection.update_many(
        {"testRunId": test_run_id}, update={"$set": {"benchmarkIds": []}}, upsert=True
    )
    metrics_result = catalog.ds.metrics.collection.bulk_write(update_queries)
    logger.info(f"Updated metrics benchmarkIds for {test_run_id}: {metrics_result}")
    return {"panels": panels_result, "metrics": metrics_result}
