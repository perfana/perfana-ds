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
from typing import Any

from pydantic import ValidationError, model_validator

from perfana_ds.schemas.base_document import BasePanelDocument
from perfana_ds.schemas.grafana.dashboard import BadPanel
from perfana_ds.schemas.grafana.panel import Panel
from perfana_ds.schemas.panel_query_request import (
    RequestModel,
)


def filter_unique_dicts(dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [x for i, x in enumerate(dicts) if x not in dicts[i + 1 :]]


class PanelWithQueryVariables(BasePanelDocument):
    panel: Panel
    query_variables: dict[str, Any]
    benchmark_ids: list[str] | None = None


class PanelDocument(BasePanelDocument):
    benchmark_ids: list[str] | None = None
    panel: Panel | BadPanel
    query_variables: dict[str, Any]
    datasource_type: str | None
    requests: list[RequestModel]
    errors: list[dict[str, Any]] | None = None
    warnings: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def validate_panel_document(cls, v: PanelDocument) -> PanelDocument:
        if v.errors is None:
            errors = []
        else:
            errors = v.errors

        if v.warnings is None:
            warnings_ = []
        else:
            warnings_ = v.warnings

        if isinstance(v.panel, BadPanel):
            try:
                Panel.validate(v.panel)
            except ValidationError as e:
                error = {
                    "type": "validationError",
                    "condition": "Panel should match schema.",
                    "message": json.loads(e.json()),
                }
                errors.append(error)
        else:
            extra_errors, extra_warnings = cls._validate_influxdb_targets(v)
            errors.extend(extra_errors)
            warnings_.extend(extra_warnings)

            extra_errors, extra_warnings = cls._validate_prometheus_targets(v)
            errors.extend(extra_errors)
            warnings_.extend(extra_warnings)

            extra_errors, extra_warnings = cls._validate_supported_panel_types(v)
            errors.extend(extra_errors)
            warnings_.extend(extra_warnings)

            extra_errors, extra_warnings = cls._validate_supported_datasources(v)
            errors.extend(extra_errors)
            warnings_.extend(extra_warnings)

            extra_errors, extra_warnings = cls._validate_has_no_transformations(v)
            errors.extend(extra_errors)
            warnings_.extend(extra_warnings)

        if len(errors) == 0:
            errors = None  # type: ignore[assignment]
        else:
            errors = filter_unique_dicts(errors)

        if len(warnings_) == 0:
            warnings_ = None  # type: ignore[assignment]
        else:
            warnings_ = filter_unique_dicts(warnings_)

        v.errors = errors
        v.warnings = warnings_
        return v

    @classmethod
    def _validate_influxdb_targets(
        cls, v: PanelDocument
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors = []
        warnings_: list[dict[str, Any]] = []
        if v.datasource_type == "influxdb":
            for target_index, target in enumerate(v.panel.targets):
                if target.rawQuery is False:
                    error = {
                        "type": "targetError",
                        "condition": "datasource_type == 'influxdb'",
                        "message": "Found panels where 'rawQuery: false'.",
                        "targetIndex": target_index + 1,
                    }
                    errors.append(error)
        return errors, warnings_

    @classmethod
    def _validate_prometheus_targets(
        cls, v: PanelDocument
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors = []
        warnings_: list[dict[str, Any]] = []
        if v.datasource_type == "prometheus":
            for target_index, target in enumerate(v.panel.targets):
                if target.expr == "":
                    error = {
                        "type": "targetError",
                        "condition": "datasource_type == 'prometheus'",
                        "message": "Found panel targets where expression is empty.",
                        "targetIndex": target_index + 1,
                    }
                    errors.append(error)
        return errors, warnings_

    @classmethod
    def _validate_supported_panel_types(
        cls, v: PanelDocument
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors = []
        warnings_: list[dict[str, Any]] = []

        supported_panel_types = ["timeseries", "stat", "graph"]
        panel = v.panel
        if panel.type not in supported_panel_types:
            errors.append(
                {
                    "type": "typeError",
                    "condition": f"panel.type in {supported_panel_types}",
                    "message": f"Panel type '{panel.type}' not supported",
                }
            )
        return errors, warnings_

    @classmethod
    def _validate_supported_datasources(
        cls, v: PanelDocument
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings_: list[dict[str, Any]] = []

        supported_datasources = ["influxdb", "prometheus"]
        datasource_type = v.datasource_type
        if datasource_type not in supported_datasources:
            warnings_.append(
                {
                    "type": "datasourceTypeWarning",
                    "condition": f"panel.datasource.type in {supported_datasources}",
                    "message": f"Datasource '{datasource_type}' might give unstable results.",
                }
            )

        return errors, warnings_

    @classmethod
    def _validate_has_no_transformations(
        cls, v: PanelDocument
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings_: list[dict[str, Any]] = []
        panel = v.panel
        if panel.transformations is not None:
            warnings_.append(
                {
                    "type": "transformationsWarning",
                    "condition": "panel.transformations is null",
                    "message": "Panel has transformations, which are ignored for analysis and "
                    "result may not match displayed values.",
                }
            )

        return errors, warnings_
