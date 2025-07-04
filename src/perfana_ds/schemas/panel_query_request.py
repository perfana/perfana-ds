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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from perfana_ds.schemas.base_document import BasePanelDocument
from perfana_ds.schemas.base_extra import BaseModelExtra


class PostRequestBody(BaseModelExtra):
    class QueryRequestBody(BaseModelExtra):
        refId: str = Field(default="A")
        datasourceId: int

    model_config = ConfigDict(populate_by_name=True)
    queries: list[QueryRequestBody]
    from_: str = Field(alias="from")
    to: str

    @field_validator("from_", "to", mode="before")
    def convert_str_to_int(cls, v: str | int) -> str:
        return str(int(float(v)))


class RequestModel(BaseModel):
    method: Literal["POST", "GET"]
    endpoint: str
    path_parameters: dict[str, Any] | None = None
    request_body: PostRequestBody | None = None


class PanelQueryResponse(BasePanelDocument):
    datasource_type: str  # Literal["influxdb", "prometheus", "pyroscope"]
    panel_type: str
    requests: list[RequestModel]
