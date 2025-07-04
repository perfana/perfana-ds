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

import asyncio
from copy import deepcopy
from typing import Any, Literal

import httpx

from perfana_ds.common.async_requests import run_async
from perfana_ds.pipelines.metrics.format_result import (
    format_query_responses_as_dataframe,
)
from perfana_ds.project_settings import Settings
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
from perfana_ds.schemas.panel_query_request import (
    PostRequestBody,
    RequestModel,
)
from perfana_ds.schemas.panel_query_result import BasePanelQueryResult
from perfana_ds.schemas.perfana.test_runs import TestRun


def query_grafana_panel_data(
    panel_queries: list[PanelDocument],
    api_headers: dict[str, str],
    settings: Settings,
) -> list[BasePanelQueryResult]:
    coro = _query_grafana_panel_data(
        panels=panel_queries, api_headers=api_headers, settings=settings
    )
    result = run_async(coro)
    return result


def batch_panel_queries(
    panels: list[PanelDocument], batch_size: int = 1
) -> list[dict[str, RequestModel | list[dict[str, PanelDocument | list[str]]]]]:
    if len(panels) == 0:
        return []

    request_batches: list[
        dict[str, RequestModel | list[dict[str, PanelDocument | list[str]]]]
    ] = []
    batch_request: RequestModel | None = None
    ref_id_mapping: list[dict[str, PanelDocument | list[str]]] = []

    for i, panel in enumerate(panels):
        if len(panel.requests) == 0:
            continue

        if (batch_request is None) or ((i + 1) % batch_size == 0):
            if batch_request is not None:
                batch_record = dict(
                    request=batch_request, ref_id_mapping=ref_id_mapping
                )
                request_batches.append(batch_record)
                ref_id_mapping = []  # reset

            batch_request = RequestModel(
                endpoint="/api/ds/query",
                method="POST",
                request_body=PostRequestBody(
                    queries=[],
                    from_=panel.requests[0].request_body.from_,
                    to=panel.requests[0].request_body.to,
                ),
            )

        panel_ref_ids = []
        for target_index, request in enumerate(panel.requests):
            for query in request.request_body.queries:
                new_query = deepcopy(query)
                new_query.refId = f"{query.refId}{i}"
                batch_request.request_body.queries.append(new_query)
                panel_ref_ids.append(new_query.refId)
                ref_id_mapping.append(
                    dict(panel=panel, target_index=target_index, ref_id=new_query.refId)
                )

    if (batch_request is not None) and (len(batch_request.request_body.queries) > 0):
        batch_record = dict(request=batch_request, ref_id_mapping=ref_id_mapping)
        request_batches.append(batch_record)
    return request_batches


async def _query_grafana_panel_data(  # noqa: PLR0912
    panels: list[PanelDocument],
    api_headers: dict[str, str],
    settings: Settings,
    batch_size: int | None = None,
) -> list[BasePanelQueryResult]:
    if batch_size is None:
        batch_size = settings.GRAFANA_BATCH_SIZE
    request_batches = batch_panel_queries(panels, batch_size=batch_size)

    transport = httpx.AsyncHTTPTransport(retries=3)
    limits = httpx.Limits(
        max_keepalive_connections=None, max_connections=settings.GRAFANA_CONCURRENCY
    )

    # make async requests
    tasks = []
    async with (
        httpx.AsyncClient(
            headers=api_headers,
            base_url=settings.GRAFANA_URL,
            timeout=httpx.Timeout(None, connect=5.0),
            transport=transport,
            limits=limits,
        ) as client,
    ):
        # make requests
        for request_batch in request_batches:
            batch_request_model: RequestModel = request_batch["request"]
            request_task = make_async_request(
                client,
                url=batch_request_model.endpoint,
                method=batch_request_model.method,
                path_parameters=batch_request_model.path_parameters,
                request_body=batch_request_model.dict(by_alias=True)["request_body"],
            )
            tasks.append(request_task)
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    # handle responses and map to panels
    panel_results = []
    for request_batch, response in zip(request_batches, responses):
        ref_id_mapping: list[dict[str, PanelDocument | list[str]]] = request_batch[
            "ref_id_mapping"
        ]

        if isinstance(response, Exception | httpx.HTTPError):
            response_results = None
        else:
            json_response = response.json()
            if (response.status_code != httpx.codes.OK) and (
                "results" not in json_response.keys()
            ):
                response_results = None
            else:
                response_results = json_response["results"]

        for ref_id_map in ref_id_mapping:
            panel: PanelDocument = deepcopy(ref_id_map["panel"])
            target_index = ref_id_map["target_index"]
            ref_id = ref_id_map["ref_id"]

            # internal client-side errors, add errors to Panel objects
            if isinstance(response, Exception | httpx.HTTPError):
                if isinstance(response, httpx.HTTPError):
                    message = "Internal client error when making request to Grafana."
                elif isinstance(response, Exception):
                    message = str(response)
                else:
                    message = ""

                if panel.errors is None:
                    panel.errors = []

                panel.errors.append(  # type: ignore
                    dict(
                        target_index=target_index,
                        status_code=None,
                        message=message,
                        type=response.__class__.__name__,
                    )
                )
                panel_data: list[dict[str, Any]] = []

            # error status of entire batch, add errors to Panel objects
            elif ("results" not in json_response.keys()) and (
                response.status_code != httpx.codes.OK
            ):
                if panel.errors is None:
                    panel.errors = []

                panel.errors.append(  # type: ignore
                    dict(
                        target_index=target_index,
                        message="Grafana request batch error.",
                        status_code=response.status_code,
                        detail=json_response.get("message", "No message."),
                        type="requestError",
                    )
                )
                panel_data = []

            # error status of query result within batch, add errors to Panel objects
            elif response_results[ref_id]["status"] != httpx.codes.OK:
                if panel.errors is None:
                    panel.errors = []

                panel.errors.append(  # type: ignore
                    dict(
                        target_index=target_index,
                        message="Grafana request returned error status.",
                        status_code=response_results[ref_id]["status"],
                        detail=response_results[ref_id]["error"],
                        type="requestError",
                    )
                )
                panel_data = []

            # status code must be 200 for panel result
            else:
                panel_data = dict(results={ref_id: response_results[ref_id]})

            panel_target_result = BasePanelQueryResult(
                target_index=target_index, data=panel_data, **panel.dict()
            )

            panel_results.append(panel_target_result)
    return panel_results


async def make_async_request(
    client: httpx.AsyncClient,
    url: str,
    path_parameters: dict[str, Any],
    method: Literal["POST", "GET"],
    request_body: dict | None,
) -> httpx.Response:
    if method == "POST":
        response = await client.post(url, params=path_parameters, json=request_body)
    elif method == "GET":
        response = await client.get(url, params=path_parameters)
    else:
        raise NotImplementedError(f"Cannot make request for {method=}")
    return response


def format_query_results_as_documents(
    test_run: TestRun, query_results: list[BasePanelQueryResult]
) -> list[PanelMetricsDocument]:
    # query_results =
    documents = format_query_responses_as_dataframe(
        test_run=test_run, panel_query_responses=query_results
    )

    return documents
