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

import pandas as pd
from pydantic import BaseModel, ConfigDict


class BaseFlamegraphDocument(BaseModel):
    test_run_id: str
    panel_id: int
    dashboard_uid: str
    application_dashboard_id: str
    updated_at: datetime | None = None


class RawFlamegraphDocument(BaseFlamegraphDocument):
    data: dict[str, Any]


class DataFrameFlamegraphDocument(BaseFlamegraphDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    data: pd.DataFrame


class TableFlamegraphDocument(BaseFlamegraphDocument):
    class TableFlamegraphRecord(BaseModel):
        name: str
        selfTimeNano: int
        selfTimedelta: str
        selfTimeString: str
        totalTimeNano: int
        totalTimedelta: str
        totalTimeString: str

    data: list[TableFlamegraphRecord]


class ComparisonFlamegraphDocument(BaseFlamegraphDocument):
    class ComparisonRecord(BaseModel):
        class ComparisonFields(BaseModel):
            self: int | float | None
            value: int | float | None
            self_fraction: float
            value_fraction: float
            n: int | float

        label: str
        test_run: ComparisonFields
        baseline: ComparisonFields
        difference: ComparisonFields
        difference_percent: ComparisonFields

    baseline_run_id: str
    data: list[ComparisonRecord]
