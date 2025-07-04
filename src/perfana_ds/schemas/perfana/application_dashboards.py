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

from pydantic import BaseModel, Field

from perfana_ds.schemas.base_extra import BaseModelExtra


class VariableMapping(BaseModel):
    name: str
    values: list[str]

    @property
    def value(self) -> str:
        if len(self.values) == 1:
            return self.values[0]
        elif len(self.values) > 1:
            return f"({'|'.join(self.values)})"
        else:
            raise ValueError(f"VariableMapping has no values: {self}")


class ApplicationDashboard(BaseModelExtra):
    id: str = Field(alias="_id")
    _class: str
    application: str
    testEnvironment: str
    grafana: str
    dashboardUid: str
    dashboardName: str
    dashboardId: int | None = None
    dashboardLabel: str
    tags: list[str] = Field(default_factory=list)
    variables: list[VariableMapping] = Field(default_factory=list)
    snapshotTimeout: int | None = None
    templateDashboardUid: str | None = None
    perfanaInfo: str | None = None
