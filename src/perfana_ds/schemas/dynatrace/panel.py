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

from pydantic import BaseModel, Field

from perfana_ds.schemas.base_extra import BaseModelExtra


class BadPanel(BaseModelExtra):
    id: str
    name: str | None = None


class TileFilter(BaseModel):
    timeframe: str | None = None
    managementZone: dict[str, Any] | None = None


class TileBounds(BaseModel):
    top: int
    left: int
    width: int
    height: int


class MetricQuery(BaseModelExtra):
    metricSelector: str
    resolution: str | None = None
    entitySelector: str | None = None
    foldTransformation: str | None = None


class Panel(BaseModelExtra):
    id: str
    name: str | None = None
    tileType: Literal[
        "DATA_EXPLORER",
        "MARKDOWN",
        "DTAQL",
        "CUSTOM_CHARTING",
        "SLO",
        "SYNTHETIC_SINGLE_WEBCHECK",
        "SYNTHETIC_SINGLE_EXT_TEST",
        "HOSTS",
        "SERVICES",
        "PROBLEMS",
        "APPLICATIONS",
        "DATABASES",
        "NETWORK",
        "LOG_ANALYTICS"
    ]
    configured: bool | None = None
    bounds: TileBounds
    tileFilter: TileFilter | None = None
    filterConfig: dict[str, Any] | None = None
    chartVisible: bool | None = None
    queries: list[MetricQuery] | None = None
    customName: str | None = None
    query: str | None = None
    markdown: str | None = None
    assignedEntities: list[str] | None = None
    metric: str | None = None