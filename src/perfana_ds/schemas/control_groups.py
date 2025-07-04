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

from datetime import datetime
from typing import Any

from pydantic import Field

from perfana_ds.schemas.base_document import BaseDocument


class ControlGroup(BaseDocument):
    application: str | None
    test_type: str | None
    test_environment: str | None
    control_group_id: str
    n_test_runs: int
    test_runs: list[str]
    last_datetime: datetime | None
    first_datetime: datetime | None
    metric_filters: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None
