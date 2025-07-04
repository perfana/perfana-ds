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

import json
from datetime import datetime
from string import Template
from typing import Any

from celery.utils.log import get_task_logger
from pymongo.collection import Collection

from perfana_ds.common.grafana_api_auth import (
    create_grafana_api_headers,
    get_grafana_api_key_from_mongo,
)
from perfana_ds.pipelines.panels.datasources import (
    get_datasources_for_panels,
)
from perfana_ds.pipelines.panels.perfana_data import PerfanaData
from perfana_ds.pipelines.panels.query_template_variables import (
    _remove_unused_query_variables,
    get_query_template_variables_from_application_dashboard,
    get_query_template_variables_from_panel,
    get_query_template_variables_from_test_run,
)
from perfana_ds.project_settings import Settings, get_settings
from perfana_ds.schemas.grafana.dashboard import Dashboard
from perfana_ds.schemas.grafana.datasource import Datasource
from perfana_ds.schemas.grafana.panel import Panel
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_query_request import RequestModel

logger = get_task_logger(__name__)


def get_datasource(
    source_item: Panel | Any,
    datasource_name_lookup: dict[str, Datasource],
    datasource_uid_lookup: dict[str, Datasource],
) -> Datasource | None:
    """Get datasource from lookup dictionaries, handling missing datasources gracefully.

    Args:
        source_item: Panel or target with datasource information
        datasource_name_lookup: Dictionary mapping datasource names to Datasource objects
        datasource_uid_lookup: Dictionary mapping datasource UIDs to Datasource objects

    Returns:
        Datasource object if found, None if datasource is missing
    """
    try:
        if isinstance(source_item.datasource, str):
            if source_item.datasource == "grafana":
                return None
            return datasource_name_lookup[source_item.datasource]
        elif source_item.datasource is not None:
            if source_item.datasource.uid == "grafana":
                return None
            return datasource_uid_lookup[source_item.datasource.uid]
        return None
    except KeyError:
        datasource_id = (
            source_item.datasource
            if isinstance(source_item.datasource, str)
            else getattr(source_item.datasource, "uid", "unknown")
        )
        logger.warning(
            f"Datasource {datasource_id} not found in available datasources. "
            "Panel queries using this datasource will be skipped."
        )
        return None


def construct_panel_documents(
    grafana_dashboards: list[Dashboard],
    perfana_data: PerfanaData,
    base_query_variables: dict[str, Any],
    datasources: list[Datasource],
) -> list[PanelDocument]:
    benchmark_ids_mapping: dict[tuple, list[str]] = {}
    for benchmark in perfana_data.benchmarks:
        lookup_key = (benchmark.dashboardLabel, benchmark.panel.id)
        if lookup_key in benchmark_ids_mapping.keys():
            benchmark_ids_mapping[lookup_key].append(benchmark.id)
        else:
            benchmark_ids_mapping[lookup_key] = [benchmark.id]

    dashboards_mapping = {x.uid: x for x in grafana_dashboards}

    datasource_name_lookup: dict[str, Datasource] = {x.name: x for x in datasources}
    datasource_uid_lookup: dict[str, Datasource] = {x.uid: x for x in datasources}

    now = datetime.utcnow()
    panel_documents = []
    for application_dashboard in perfana_data.application_dashboards:
        dashboard = dashboards_mapping.get(application_dashboard.dashboardUid)
        if dashboard is None:
            logger.warning(
                f"Dashboard {application_dashboard.dashboardUid} not found, skipping"
            )
            continue

        dashboard_query_variables = (
            get_query_template_variables_from_application_dashboard(
                application_dashboard
            )
        )
        for panel in dashboard.dashboard.panels:
            if not isinstance(panel, Panel) or panel.type == "row":
                continue
            panel_datasource = get_datasource(
                panel, datasource_name_lookup, datasource_uid_lookup
            )

            if panel_datasource is None:
                # Create minimal panel document for panels without datasource
                panel_documents.append(
                    PanelDocument(
                        test_run_id=perfana_data.test_run.testRunId,
                        application_dashboard_id=application_dashboard.id,
                        dashboard_uid=application_dashboard.dashboardUid,
                        dashboard_label=application_dashboard.dashboardLabel,
                        panel_id=panel.id,
                        panel_title=panel.title,
                        panel=panel,
                        query_variables={},
                        benchmark_ids=benchmark_ids_mapping.get(
                            (application_dashboard.dashboardLabel, panel.id)
                        ),
                        datasource_type=None,
                        requests=[],
                        updated_at=now,
                    )
                )
                continue

            # Process panel with valid datasource
            panel_query_variables = get_query_template_variables_from_panel(panel)
            query_variables = (
                base_query_variables | dashboard_query_variables | panel_query_variables
            )
            query_variables = _remove_unused_query_variables(query_variables, panel)

            panel_queries_body = []
            skip_panel = False

            for target in panel.targets:
                target_datasource = get_datasource(
                    target, datasource_name_lookup, datasource_uid_lookup
                )

                if (
                    target_datasource is None
                    or target_datasource.id != panel_datasource.id
                ):
                    logger.warning(
                        f"Invalid target datasource for panel {panel.id}, skipping panel"
                    )
                    skip_panel = True
                    break

                target_json = target.json()
                target_json_resolved = Template(target_json).safe_substitute(
                    **query_variables
                )
                target_dict = json.loads(target_json_resolved)
                target_dict["datasourceId"] = panel_datasource.id
                panel_queries_body.append(target_dict)

            if skip_panel:
                continue

            panel_query_request = RequestModel(
                method="POST",
                endpoint="/api/ds/query",
                path_parameters={
                    "ds_type": panel_datasource.type,
                    "requestId": f"{application_dashboard.id}:{panel.id}",
                },
                request_body={
                    "from": perfana_data.test_run.start.timestamp() * 1000,
                    "to": perfana_data.test_run.end.timestamp() * 1000,
                    "queries": panel_queries_body,
                },
            )

            panel_documents.append(
                PanelDocument(
                    test_run_id=perfana_data.test_run.testRunId,
                    application_dashboard_id=application_dashboard.id,
                    dashboard_uid=application_dashboard.dashboardUid,
                    dashboard_label=application_dashboard.dashboardLabel,
                    panel_id=panel.id,
                    panel_title=panel.title,
                    panel=panel,
                    query_variables=query_variables,
                    benchmark_ids=benchmark_ids_mapping.get(
                        (application_dashboard.dashboardLabel, panel.id)
                    ),
                    datasource_type=panel_datasource.type,
                    requests=[panel_query_request],
                    updated_at=now,
                )
            )

    return panel_documents


def create_panel_documents(
    perfana_data: PerfanaData,
    grafanas_collection: Collection,
    settings: Settings | None = None,
) -> list[PanelDocument]:
    if settings is None:
        settings = get_settings()
    grafana_api_key = get_grafana_api_key_from_mongo(grafanas_collection)
    grafana_api_headers = create_grafana_api_headers(grafana_api_key)
    grafana_dashboards = perfana_data.dashboards
    test_run_query_variables = get_query_template_variables_from_test_run(
        perfana_data.test_run
    )

    panels = [
        panel
        for dashboard in grafana_dashboards
        for panel in dashboard.dashboard.panels
    ]
    datasources = get_datasources_for_panels(panels, grafana_api_headers, settings)

    panel_documents = construct_panel_documents(
        grafana_dashboards=grafana_dashboards,
        perfana_data=perfana_data,
        base_query_variables=test_run_query_variables,
        datasources=datasources,
    )

    return panel_documents
