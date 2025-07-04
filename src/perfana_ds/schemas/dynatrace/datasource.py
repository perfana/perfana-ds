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

from typing import Any

from pydantic import BaseModel, Field


class Datasource(BaseModel):
    id: str
    name: str
    type: str = "dynatrace"
    url: str
    token: str | None = None
    apiToken: str | None = None
    version: str | None = None
    entitySelectorMode: str | None = None
    jsonData: dict[str, Any] = Field(default_factory=dict)