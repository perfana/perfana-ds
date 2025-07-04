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

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from perfana_ds.schemas.base_extra import BaseModelExtra
from perfana_ds.schemas.grafana.datasource import Datasource


class GridPos(BaseModel):
    h: int
    w: int
    x: int
    y: int


class PanelDataSource(BaseModel):
    uid: str
    type: str


def _datasource_name_from_string_as_list(
    datasource: PanelDataSource | dict[str, Any]
) -> str | PanelDataSource:
    """Field validator for Datasource fields."""
    if isinstance(datasource, dict) and all(
        [str(i) in datasource.keys() for i in range(len(datasource.keys()))]
    ):
        sorted_integer_keys = sorted([int(key) for key in datasource.keys()])
        sorted_values = [datasource[str(key)] for key in sorted_integer_keys]
        result = "".join(sorted_values)
    else:
        result = datasource  # type: ignore [assignment]
    return result


class RowTarget(BaseModel):
    class PanelDataSource(BaseModel):
        uid: Literal["grafana"]
        type: Literal["datasource"]

    datasource: PanelDataSource
    refId: str


class AzureMonitorTarget(BaseModelExtra):
    """Azure Monitor target for Grafana panels."""

    datasource: PanelDataSource | Datasource | str
    refId: str
    queryType: Literal["Azure Monitor"]
    subscription: str
    subscriptions: list[str] = Field(default_factory=list)
    azureMonitor: dict[str, Any] = Field(default_factory=dict)

    @field_validator("datasource", mode="before")
    @classmethod
    def datasource_name_from_string_as_list(
        cls, datasource: PanelDataSource | dict[str, Any]
    ) -> str | PanelDataSource:
        return _datasource_name_from_string_as_list(datasource)


class InfluxdbTarget(BaseModelExtra):
    datasource: PanelDataSource | Datasource | str
    rawQuery: bool = False
    query: str = ""
    alias: str | dict[str, Any] | None = None
    measurement: str
    resultFormat: str

    @field_validator("datasource", mode="before")
    @classmethod
    def datasource_name_from_string_as_list(
        cls, datasource: PanelDataSource | dict[str, Any]
    ) -> str | PanelDataSource:
        return _datasource_name_from_string_as_list(datasource)


class PrometheusTarget(BaseModelExtra):
    datasource: PanelDataSource | str
    expr: str
    legendFormat: str = ""
    instant: bool = False

    @field_validator("datasource", mode="before")
    @classmethod
    def datasource_name_from_string_as_list(
        cls, datasource: PanelDataSource | dict[str, Any]
    ) -> str | PanelDataSource:
        return _datasource_name_from_string_as_list(datasource)


class FlamegraphTarget(BaseModelExtra):
    datasource: PanelDataSource | str
    groupBy: list[str]
    labelSelector: str
    profileTypeId: str
    queryType: str
    refId: str | None = None

    @field_validator("datasource", mode="before")
    @classmethod
    def datasource_name_from_string_as_list(
        cls, datasource: PanelDataSource | dict[str, Any]
    ) -> str | PanelDataSource:
        return _datasource_name_from_string_as_list(datasource)


# Add this new class alongside the other target classes


class Panel(BaseModelExtra):
    id: int
    type: Literal[
        "heatmap",
        "timeseries",
        "table",
        "histogram",
        "stat",
        "row",
        "flamegraph",
        "graph",
    ]
    title: str
    interval: str | None = None
    targets: (
        list[
            InfluxdbTarget
            | RowTarget
            | PrometheusTarget
            | FlamegraphTarget
            | AzureMonitorTarget
        ]
        | None
    ) = None
    # gridPos: GridPos
    datasource: str | PanelDataSource | Datasource | None = None
    transformations: list[dict[str, Any]] | None = None
    fieldConfig: dict[str, Any] = Field(default_factory=dict)

    @field_validator("datasource", mode="before")
    @classmethod
    def datasource_name_from_string_as_list(
        cls, value: PanelDataSource | dict[str, Any]
    ) -> str | PanelDataSource:
        return _datasource_name_from_string_as_list(value)
