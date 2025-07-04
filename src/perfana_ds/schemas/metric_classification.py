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

from bson import ObjectId
from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from perfana_ds.schemas.base_document import BaseDocument


class MetricClassification(BaseDocument):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        arbitrary_types_allowed=True,
    )
    id: str | None = Field(None, alias="_id")
    application: str | None = None
    test_environment: str | None = None
    test_type: str | None = None
    dashboard_uid: str | None = None
    dashboard_label: str | None = None
    application_dashboard_id: str | None = None
    panel_id: int | None = None
    panel_title: str | None = None
    metric_name: str | None = None
    regex: bool = False
    metric_classification: str | None = None
    higher_is_better: bool | None = None

    @field_validator("id", mode="before")
    @classmethod
    def object_id_to_str(cls, v: ObjectId | str) -> str:
        if isinstance(v, ObjectId):
            v = str(v)
        return v
