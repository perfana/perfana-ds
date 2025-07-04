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

from pydantic import BaseModel

from perfana_ds.schemas.base_extra import BaseModelExtra
from perfana_ds.schemas.grafana.panel import Panel, PanelDataSource


class BadPanel(BaseModelExtra):
    id: int
    title: str | None = None


class Dashboard(BaseModelExtra):
    class Meta(BaseModel):
        type: str
        slug: str
        created: datetime
        updated: datetime
        version: int

    class DashboardJson(BaseModelExtra):
        class Annotations(BaseModel):
            list: list[dict[str, Any]]

        class Templating(BaseModelExtra):
            class TemplatingValue(BaseModel):
                class CurrentValue(BaseModel):
                    selected: bool
                    text: str
                    value: Any

                current: CurrentValue | dict | None = None
                datasource: PanelDataSource | str | None = None
                name: str
                regex: str | None = None
                definition: str | None = None

            list: list[TemplatingValue]

        id: int
        uid: str
        version: int
        title: str
        annotations: Annotations
        tags: list[str]
        panels: list[Panel | BadPanel]
        templating: Templating

    uid: str
    meta: dict
    dashboard: DashboardJson
