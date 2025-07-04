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

from celery.utils.log import get_task_logger
from pydantic import parse_obj_as
from pymongo.collection import Collection

from perfana_ds.common.grafana_api_auth import (
    create_grafana_api_headers,
    get_grafana_api_key_from_mongo,
)
from perfana_ds.pipelines.metrics.query_panels import (
    format_query_results_as_documents,
    query_grafana_panel_data,
)
from perfana_ds.project_settings import Settings, get_settings
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def get_panel_metrics(
    test_run: TestRun,
    panel_documents: list[PanelDocument],
    grafanas_collection: Collection,
    settings: Settings | None = None,
) -> list[PanelMetricsDocument]:
    if settings is None:
        settings = get_settings()

    grafana_api_key = get_grafana_api_key_from_mongo(grafanas_collection)
    grafana_api_headers = create_grafana_api_headers(grafana_api_key)

    panel_documents_without_errors = [
        panel_document
        for panel_document in panel_documents
        if panel_document.errors is None
    ]
    panel_documents_with_errors = [
        panel_document
        for panel_document in panel_documents
        if panel_document.errors is not None
    ]

    logger.info(
        f"Making grafana metrics requests for {len(panel_documents_without_errors)} panels."
    )
    raw_result = query_grafana_panel_data(
        panel_queries=panel_documents_without_errors,
        api_headers=grafana_api_headers,
        settings=settings,
    )

    logger.info(f"Parse {len(raw_result)} query responses.")
    result_documents = format_query_results_as_documents(
        test_run=test_run, query_results=raw_result
    )
    logger.info(f"Formatted {len(raw_result)} query responses as dictionaries.")
    results_from_panels_with_errors = parse_obj_as(
        list[PanelMetricsDocument],
        [
            dict(data=[], **(x.dict()) | dict(updated_at=datetime.utcnow()))
            for x in panel_documents_with_errors
        ],
    )
    logger.info(f"Validated {len(raw_result)} query responses.")
    metric_doc_results = result_documents + results_from_panels_with_errors
    result = combine_metric_docs(metric_doc_results)
    logger.info(f"Finished parsing {len(raw_result)} panel metric documents.")
    return result


def combine_metric_docs(metric_docs: list[PanelMetricsDocument]):
    metrics_combined: dict[tuple(str, str, int), PanelMetricsDocument] = {}
    for metric in metric_docs:
        key = (metric.test_run_id, metric.application_dashboard_id, metric.panel_id)
        if key not in metrics_combined:
            metrics_combined[key] = metric
        else:
            metrics_combined[key].data.extend(metric.data)
    result = list(metrics_combined.values())
    return result


def get_benchmark_panel_metrics(
    test_run: TestRun,
    panel_documents: list[PanelDocument],
    grafanas_collection: Collection,
    settings: Settings | None = None,
    **kwargs,
):
    panel_documents = [
        panel_document
        for panel_document in panel_documents
        if panel_document.benchmark_ids is not None
    ]
    return get_panel_metrics(
        test_run=test_run,
        panel_documents=panel_documents,
        grafanas_collection=grafanas_collection,
        settings=settings,
    )


def get_non_benchmark_panel_metrics(
    test_run: TestRun,
    panel_documents: list[PanelDocument],
    grafanas_collection: Collection,
    settings: Settings | None = None,
    **kwargs,
):
    panel_documents = [
        panel_document
        for panel_document in panel_documents
        if panel_document.benchmark_ids is None
    ]
    return get_panel_metrics(
        test_run=test_run,
        panel_documents=panel_documents,
        grafanas_collection=grafanas_collection,
        settings=settings,
    )
