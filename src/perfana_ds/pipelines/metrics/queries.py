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

# from copy import deepcopy
# from string import Template
#
# from perfana_ds.pipelines.metrics.query_panels import (
#     query_grafana_panel_data,
# )
# from perfana_ds.project_settings import Settings
# from perfana_ds.schemas.grafana.datasource import Datasource
# from perfana_ds.schemas.grafana.panel import Panel
# from perfana_ds.schemas.panel_document import PanelWithQueryVariables
# from perfana_ds.schemas.panel_query_request import PanelPostQueryResponse
# from perfana_ds.schemas.panel_query_result import PrometheusPanelQueryResult
# from perfana_ds.schemas.perfana.test_runs import TestRun
#
#
# def get_datasource_lookups(
#     datasources: list[Datasource],
# ) -> tuple[dict[str, Datasource], dict[str, Datasource]]:
#     return (
#         {datasource.name: datasource for datasource in datasources},
#         {datasource.uid: datasource for datasource in datasources},
#     )
#
#
# def get_datasource(
#     panel: Panel,
#     datasource_name_lookup: dict[str, Datasource],
#     datasource_uid_lookup: dict[str, Datasource],
# ) -> Datasource:
#     return (
#         datasource_name_lookup[panel.datasource]
#         if isinstance(panel.datasource, str)
#         else datasource_uid_lookup[panel.datasource.uid]
#     )
#
#
# def process_targets_and_create_query_request(
#     test_run: TestRun, panel: PanelWithQueryVariables, datasource
# ):
#     queries = []
#     for target in panel.panel.targets:
#         if target.expr == "":
#             continue
#
#         new_target = deepcopy(target)
#         new_target.expr = Template(new_target.expr).safe_substitute(
#             **panel.query_variables
#         )
#         new_target.instant = False  # Always non-instant request
#         query = new_target.dict() | dict(
#             datasourceId=datasource.id, datasource=datasource.dict()
#         )
#         queries.append(query)
#
#     return PanelPostQueryResponse.QueryRequest(
#         method="POST",
#         endpoint="/api/ds/query",
#         path_parameters=None,
#         request_body={
#             "from": test_run.start.timestamp() * 1000,
#             "to": test_run.end.timestamp() * 1000,
#             "queries": queries,
#         },
#     )
#
#
# def get_test_run_panel_queries_prometheus(
#     test_run: TestRun,
#     panel_responses: list[PanelWithQueryVariables],
#     datasources: list[Datasource],
# ) -> list[PanelPostQueryResponse]:
#     datasource_name_lookup, datasource_uid_lookup = get_datasource_lookups(datasources)
#
#     panel_query_responses = []
#     for panel_with_query_variables in panel_responses:
#         panel = panel_with_query_variables.panel
#
#         datasource = get_datasource(
#             panel, datasource_name_lookup, datasource_uid_lookup
#         )
#         if datasource.type != "prometheus":
#             continue
#
#         query_request = process_targets_and_create_query_request(
#             test_run, panel_with_query_variables, datasource
#         )
#         panel_query_response = PanelPostQueryResponse(
#             datasource_type="prometheus",
#             panel_type=panel.type,
#             requests=[query_request],
#             **panel_with_query_variables.dict(),
#         )
#
#         panel_query_responses.append(panel_query_response)
#
#     return panel_query_responses
#
#
# def query_grafana_panel_data_prometheus(
#     panel_queries: list[PanelPostQueryResponse],
#     api_headers: dict[str, str],
#     settings: Settings,
#     **kwargs,
# ) -> list[PrometheusPanelQueryResult]:
#     query_results = query_grafana_panel_data(
#         panel_queries, api_headers=api_headers, settings=settings
#     )
#     result = [PrometheusPanelQueryResult.parse_obj(x.dict()) for x in query_results]
#     return result
