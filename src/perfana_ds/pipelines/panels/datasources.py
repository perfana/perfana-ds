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

import httpx
from celery.utils.log import get_task_logger

from perfana_ds.common.async_requests import get_requests_async
from perfana_ds.project_settings import Settings
from perfana_ds.schemas.grafana.datasource import Datasource
from perfana_ds.schemas.grafana.panel import Panel

logger = get_task_logger(__name__)


def get_datasources_for_panels(
    panels: list[Panel],
    api_headers: dict[str, str],
    settings: Settings,
) -> list[Datasource]:
    """Get all Datasources from Grafana HTTP API that used in this test run's panels."""
    datasource_uids = []
    datasource_names = []
    for i, panel in enumerate(panels):
        # skip badly validated panels
        if not isinstance(panel, Panel):
            logger.warning(
                f"Skipping invalid panel at index {i}. Expected Panel instance but got {type(panel).__name__}. "
                f"Panel data: {panel}"
            )
            continue

        datasource = panel.datasource
        if isinstance(datasource, str):
            if datasource != "grafana":
                datasource_names.append(datasource)
        elif (datasource is not None) and (datasource.uid != "grafana"):
            datasource_uids.append(datasource.uid)

    get_requests = [
        {"url": f"/api/datasources/uid/{datasource_uid}"}
        for datasource_uid in set(datasource_uids)
    ] + [
        {"url": f"/api/datasources/name/{datasource_name}"}
        for datasource_name in set(datasource_names)
    ]

    responses = get_requests_async(
        base_url=settings.GRAFANA_URL,
        client_headers=api_headers,
        get_requests=get_requests,
    )

    datasources_with_duplicates = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            logger.warning(
                f"Error fetching datasource: {get_requests[i]}. Error: {type(response)}. "
                "Panels using this datasource will be skipped."
            )
            continue
        elif response.status_code != httpx.codes.OK:
            logger.warning(
                f"Error fetching datasource: {get_requests[i]}. "
                f"Status: {response.status_code}. Response: {response.text}. "
                "Panels using this datasource will be skipped."
            )
            continue
        else:
            response_json = response.json()
            datasources_with_duplicates.append(Datasource.parse_obj(response_json))

    # drop duplicates
    datasources = [
        x
        for i, x in enumerate(datasources_with_duplicates)
        if x not in datasources_with_duplicates[:i]
    ]

    return datasources
