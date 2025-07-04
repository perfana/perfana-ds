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

from typing import Any

from perfana_ds.schemas.grafana.panel import Panel
from perfana_ds.schemas.panel_document import (
    PanelDocument,
    PanelWithQueryVariables,
)
from perfana_ds.schemas.perfana.application_dashboards import (
    ApplicationDashboard,
)
from perfana_ds.schemas.perfana.test_runs import TestRun


def get_query_template_variables_from_application_dashboard(
    application_dashboard: ApplicationDashboard,
) -> dict[str, Any]:
    query_variables = {
        variable.name: variable.value for variable in application_dashboard.variables
    }
    return query_variables


def get_query_template_variables_from_test_run(test_run: TestRun) -> dict[str, Any]:
    query_variables = {
        "system_under_test": test_run.application,
        "test_environment": test_run.testEnvironment,
        "timeFilter": (
            f"time >= {int((test_run.start).timestamp() * 1000)}ms "
            f"AND time <= {int((test_run.end).timestamp() * 1000)}ms"
        ),
    }
    return query_variables


def get_query_template_variables_from_panel(panel: Panel) -> dict[str, Any]:
    query_variables = {
        "interval": panel.interval,
        "__interval": panel.interval,
    }
    return query_variables


def _remove_unused_query_variables(query_variables: dict[str, Any], panel: Panel):
    keys_to_remove = set(query_variables.keys())
    panel_json = panel.json()
    keys_to_keep = []
    for key in keys_to_remove:
        if f"${key}" in panel_json:
            keys_to_keep.append(key)
    keys_to_remove -= set(keys_to_keep)

    result = {
        key: value
        for key, value in query_variables.items()
        if key not in keys_to_remove
    }
    return result


def create_panel_response_lookup_by_dashboard_uid(
    panel_responses: list[PanelWithQueryVariables | PanelDocument],
) -> dict[str, dict[int, Panel]]:
    unique_dashboard_uids = set(
        [panel_response.dashboard_uid for panel_response in panel_responses]
    )
    lookup = {
        dashboard_uid: {
            panel_response.panel_id: panel_response.panel
            for panel_response in panel_responses
            if panel_response.dashboard_uid == dashboard_uid
        }
        for dashboard_uid in unique_dashboard_uids
    }
    return lookup
