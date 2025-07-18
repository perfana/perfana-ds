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

from datetime import datetime
from typing import Any

from perfana_ds.schemas.base_document import BaseDocument, BasePanelDocument


class PanelMetricsRecord(BaseDocument):
    metric_name: str | None
    time: datetime | None
    timestep: float | None
    ramp_up: bool | None
    value: float | None


class PanelMetricsDocument(BasePanelDocument):
    errors: list[dict[str, Any]] | None
    benchmark_ids: list[str] | None = None
    data: list[PanelMetricsRecord]
