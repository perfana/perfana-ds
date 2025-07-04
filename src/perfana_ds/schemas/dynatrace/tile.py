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


class BadTile(BaseModelExtra):
    type: str
    title: str | None = None


class Davis(BaseModel):
    enabled: bool | None = None
    davisVisualization: dict[str, Any] | None = None


class VisualizationSettings(BaseModelExtra):
    thresholds: list[Any] = Field(default_factory=list)
    chartSettings: dict[str, Any] = Field(default_factory=dict)
    singleValue: dict[str, Any] = Field(default_factory=dict)
    table: dict[str, Any] = Field(default_factory=dict)
    honeycomb: dict[str, Any] = Field(default_factory=dict)
    histogram: dict[str, Any] = Field(default_factory=dict)
    unitsOverrides: list[dict[str, Any]] = Field(default_factory=list)


class QuerySettings(BaseModel):
    maxResultRecords: int | None = None
    defaultScanLimitGbytes: int | None = None
    maxResultMegaBytes: int | None = None
    defaultSamplingRatio: int | None = None
    enableSampling: bool | None = None


class DataTile(BaseModelExtra):
    type: Literal["data"]
    title: str
    query: str
    davis: Davis | None = None
    visualization: str | None = None
    visualizationSettings: VisualizationSettings | None = None
    querySettings: QuerySettings | None = None


class MarkdownTile(BaseModelExtra):
    type: Literal["markdown"]
    title: str | None = None
    content: str


# Union type for all tile types
Tile = DataTile | MarkdownTile