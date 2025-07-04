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

from celery.utils.log import get_task_logger
from httpx import RequestError
from pydantic import ValidationError, parse_obj_as

from perfana_ds.common.async_requests import get_requests_async
from perfana_ds.project_settings import Settings
from perfana_ds.schemas.grafana.dashboard import Dashboard
from perfana_ds.schemas.perfana.application_dashboards import (
    ApplicationDashboard,
)

logger = get_task_logger(__name__)


def get_grafana_dashboards_from_api(
    dashboard_uids: list[str], api_headers: dict[str, str], settings: Settings
) -> list[Dashboard]:
    """Get a list of dashboards by their uid through the Grafana HTTP API at /api/dashboards/uid/{uid} for multiple of uids."""
    get_requests = [
        {"url": f"api/dashboards/uid/{dashboard_uid}"}
        for dashboard_uid in dashboard_uids
    ]
    responses = get_requests_async(
        base_url=settings.GRAFANA_URL,
        client_headers=api_headers,
        get_requests=get_requests,
        return_exceptions=True,
    )

    dashboards = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            raise RequestError(
                f"Error with request to Grafana: {get_requests[i]}"
            ) from response
        else:
            dashboards.append(response.json())
    for dashboard in dashboards:
        dashboard["uid"] = dashboard["dashboard"]["uid"]

    try:
        result = parse_obj_as(list[Dashboard], dashboards)
    except ValidationError as e:
        errors = e.errors()
        error_indices = list(set([error["loc"][0] for error in errors]))

        for error_idx in error_indices:
            logger.error(
                f"Validation errors for dashboard '{dashboards[error_idx]['uid']}':\n{str(e)}"
            )
            logger.debug(
                f"Validation errors for dashboard '{dashboards[error_idx]['uid']}':\n{str(e)}"
            )
        dashboards = [x for i, x in enumerate(dashboards) if i not in error_indices]
        result = parse_obj_as(list[Dashboard], dashboards)
    return result


def get_grafana_dashboards_for_application_dashboards(
    application_dashboards: list[ApplicationDashboard],
    api_headers: dict[str, str],
    settings: Settings,
) -> list[Dashboard]:
    """Get dashboards from Grafana API that match the applicationDashboards."""
    dashboard_uids = list(
        set(
            [
                application_dashboard.dashboardUid
                for application_dashboard in application_dashboards
            ]
        )
    )
    response = get_grafana_dashboards_from_api(
        dashboard_uids=dashboard_uids, api_headers=api_headers, settings=settings
    )
    return response
