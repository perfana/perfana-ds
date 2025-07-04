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

from pydantic import Field, computed_field

from perfana_ds.schemas.base_document import BaseDocument


class ControlRunDocument(BaseDocument):
    baseline_mode: bool = Field(
        False, description="Baseline mode runs are always included in control."
    )
    debug_mode: bool = Field(
        False,
        description="Debug mode runs are never included in control, priority over baselineMode.",
    )
    test_run_id: str = Field(
        ..., description="Test run ID is a unique index of this collection."
    )
    test_run_start: datetime = Field(
        ..., description="Test run start datetime copied for convenience."
    )
    denied_differences: bool = Field(
        ..., description="True if ADAPT found differences that the user DENIED."
    )
    tbd_differences: bool = Field(
        ...,
        description="True if ADAPT found differences that the user has not accepted or denied yet.",
    )
    tbd_differences_allowed: bool = Field(
        True,
        description="True if run should be allowed in control if TBD differences are present.",
    )
    meets_requirement: bool = Field(
        ..., description="True if test run passes SLO checks."
    )
    updated_at: datetime = Field(..., description="Last updated timestamp")

    @computed_field  # type: ignore[misc]
    @property
    def include_in_control(self) -> bool:
        if self.debug_mode is True:
            include_in_control_group = False
        elif self.baseline_mode is True:
            include_in_control_group = True
        elif (
            self.denied_differences
            or self.meets_requirement is False
            or (self.tbd_differences is True and self.tbd_differences_allowed is False)
        ):
            include_in_control_group = False
        else:
            include_in_control_group = True

        return include_in_control_group
