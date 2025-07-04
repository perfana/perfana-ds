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

from perfana_ds.schemas.panel_document import PanelDocument


class BasePanelQueryResult(PanelDocument):
    target_index: int
    data: list[dict[str, Any]] | dict[str, Any]


class InfluxdbPanelQueryResult(BasePanelQueryResult):
    datasource_type: Literal["influxdb"] = "influxdb"


class PrometheusPanelQueryResult(BasePanelQueryResult):
    datasource_type: Literal["prometheus"] = "prometheus"


class FlamegraphPanelQueryResult(BasePanelQueryResult):
    datasource_type: Literal["pyroscope"] = "pyroscope"


class DynatracePanelQueryResult(BasePanelQueryResult):
    datasource_type: Literal["dynatrace"] = "dynatrace"
