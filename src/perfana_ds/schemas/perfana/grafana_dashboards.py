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

from pydantic import BaseModel, Field, Json

from perfana_ds.schemas.base_extra import BaseModelExtra
from perfana_ds.schemas.perfana.application_dashboards import VariableMapping


class GrafanaDashboard(BaseModelExtra):
    """grafanaDashboards document from the Perfana database."""

    class Panel(BaseModel):
        id: int
        title: str
        description: str | None
        yAxesFormat: str | None
        repeat: str | None

    class NamedVariables(BaseModel):
        name: str | None = None

    id: str = Field(alias="_id")
    grafana: str
    uid: str
    applicationDashboardVariables: list[VariableMapping] | None
    datasourceType: (
        str  # Literal["influxdb", "prometheus", "grafana-pyroscope-datasource"]
    )
    grafanaJson: Json | None
    panels: list[Panel]
    slug: str
    name: str
    uri: str
    tags: list[str] = Field(default_factory=list)
    templateCreateDate: datetime
    templateDashboardUid: str | None
    templateProfile: str | None
    templateTestRunVariables: list[dict[str, str]] | None
    templatingVariables: list[dict[str, Any]]
    updated: datetime
    usedBySUT: list[str] = Field(default_factory=list)
    variables: list[NamedVariables] = Field(default_factory=list)
