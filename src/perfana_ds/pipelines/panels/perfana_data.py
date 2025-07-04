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

from __future__ import annotations

import json
import warnings
from typing import Any

from celery.utils.log import get_task_logger
from pydantic import BaseModel, parse_obj_as
from pydantic_core import ValidationError
from pymongo.collection import Collection

from perfana_ds.schemas.base_document import BasePanelDocument
from perfana_ds.schemas.grafana.dashboard import Dashboard
from perfana_ds.schemas.grafana.panel import Panel
from perfana_ds.schemas.perfana.application_dashboards import (
    ApplicationDashboard,
)
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def get_application_dashboards_for_test_run(
    application_dashboards_collection: Collection, test_run: TestRun
):
    test_run_id = test_run.testRunId
    application = test_run.application
    cursor = application_dashboards_collection.find(
        {
            "application": application,
            "testEnvironment": test_run.testEnvironment,
        }
    )
    documents = list(cursor)
    if len(documents) == 0:
        warnings.warn(
            f"No application dashboards for testRunId={test_run_id}, "
            f"{application=}, {test_run.testEnvironment=}."
        )
    application_dashboards = parse_obj_as(list[ApplicationDashboard], documents)
    return application_dashboards


def get_grafana_dashboards_for_application_dashboards(
    grafana_dashboards_collection: Collection,
    application_dashboards: list[ApplicationDashboard],
) -> list[Dashboard]:
    cursor = grafana_dashboards_collection.find(
        {"uid": {"$in": [x.dashboardUid for x in application_dashboards]}}
    )
    documents = list(cursor)
    if len(documents) == 0:
        raise FileNotFoundError(
            "No grafana dashboards matching any application dashboards."
        )

    dashboard_dicts = []
    for document in documents:
        dashboard_dict = json.loads(document["grafanaJson"])
        try:
            dashboard_dict["uid"] = dashboard_dict["dashboard"]["uid"]
        except KeyError:
            pass
        dashboard_dicts.append(dashboard_dict)

    # only keep dashboards that match validation schema, skip otherwise
    try:
        grafana_dashboards = parse_obj_as(list[Dashboard], dashboard_dicts)
    except ValidationError as e:
        errors = e.errors()
        error_indices = list(set([error["loc"][0] for error in errors]))

        for error_idx in error_indices:
            logger.error(
                f"Validation errors for dashboard '{dashboard_dicts[error_idx]['uid']}':\n{str(e)}"
            )
            logger.debug(
                f"Validation errors for dashboard '{dashboard_dicts[error_idx]['uid']}':\n{str(e)}"
            )
        dashboard_dicts = [
            x for i, x in enumerate(dashboard_dicts) if i not in error_indices
        ]
        grafana_dashboards = parse_obj_as(list[Dashboard], dashboard_dicts)

    return grafana_dashboards


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


def get_benchmarks_for_test_run(
    test_run: TestRun,
    benchmarks_collection: Collection,
) -> list[Benchmark]:
    """Return a list of benchmarks for a test run."""
    filters = {
        "application": test_run.application,
        "testType": test_run.testType,
        "testEnvironment": test_run.testEnvironment,
    }
    cursor = benchmarks_collection.find(filters)
    documents = list(cursor)
    if len(documents) == 0:
        warnings.warn(
            f"No panels with benchmarks found for {test_run.testRunId=} with {filters=}"
        )
    results = parse_obj_as(list[Benchmark], documents)
    return results


def split_benchmark_panels(
    panels: list[BasePanelDocument],
    benchmarks: list[Benchmark],
):
    benchmark_panels = []
    non_benchmark_panels = []
    benchmark_panel_id_tuples = [
        (benchmark.dashboardUid, benchmark.panel.id) for benchmark in benchmarks
    ]
    for panel in panels:
        panel_id_tuple = (panel.dashboard_uid, panel.panel_id)
        if panel_id_tuple in benchmark_panel_id_tuples:
            benchmark_panels.append(panel)
        else:
            non_benchmark_panels.append(panel)
    return benchmark_panels, non_benchmark_panels


class PerfanaData(BaseModel):
    test_run_id: str
    test_run: TestRun
    application_dashboards: list[ApplicationDashboard]
    benchmarks: list[Benchmark]
    dashboards: list[Dashboard]
