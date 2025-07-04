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
from typing import Literal

from bson import ObjectId
from pydantic import ConfigDict, Field

from perfana_ds.schemas.base_document import BaseDocument


class AdaptConclusionDocument(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    class Details(BaseDocument):
        model_config = ConfigDict(extra="allow")
        message: str

    test_run_id: str
    control_group_id: str | None
    regressions: list[ObjectId] = Field(
        ..., description="List dsAdaptResult document ids with regression"
    )
    improvements: list[ObjectId] = Field(
        ..., description="List dsAdaptResult document ids with improvements"
    )
    differences: list[ObjectId] = Field(
        ..., description="List dsAdaptResult document ids with regressions"
    )
    conclusion: Literal["REGRESSION", "PASSED", "SKIPPED", "ERROR", "UNRELIABLE"]
    details: Details
    updated_at: datetime
