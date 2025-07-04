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

from bson import ObjectId
from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from perfana_ds.schemas.base_document import BaseDocument


class CompareConfigs(BaseDocument):
    class StatisticConfig(BaseDocument):
        """Config for which statistic is used to compare"""

        value: str = "median"
        source: str = "default"

    class IqrConfig(BaseDocument):
        """Config for IQR difference threshold"""

        value: float = 2
        source: str = "default"

    class PctConfig(BaseDocument):
        """Config for percentage difference threshold"""

        value: float = 0.15
        source: str = "default"

    class AbsConfig(BaseDocument):
        """Config for percentage difference threshold"""

        value: float | None = None
        source: str = "default"

    class NConfig(BaseDocument):
        """Config for number of required observations"""

        value: int = 5
        source: str = "default"

    class HigherIsBetterConfig(BaseDocument):
        """Config for higher is better, can be None"""

        value: bool | None = None
        source: str = "default"

    class IgnoreConfig(BaseDocument):
        """Config for ignoring adapt result in conclusion"""

        value: bool | None = False
        source: str = "default"

        @field_validator("value", mode="before")
        @classmethod
        def default_if_none(cls, v) -> bool:
            if v is None:
                v = False
            return v

    class DefaultValueIfControlGroupMissingConfig(BaseDocument):
        """Config for default value to use when control group is missing"""

        value: float | None = None
        source: str = (
            "panel"  # "panel" applies to all metrics in panel, "metric" applies to specific metric
        )

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        arbitrary_types_allowed=True,
    )
    statistic: StatisticConfig = Field(default_factory=StatisticConfig)
    iqr_threshold: IqrConfig = Field(default_factory=IqrConfig)
    pct_threshold: PctConfig = Field(default_factory=PctConfig)
    abs_threshold: AbsConfig = Field(default_factory=AbsConfig)
    n_threshold: NConfig = Field(default_factory=NConfig)
    ignore: IgnoreConfig = Field(default_factory=IgnoreConfig)
    default_value_if_control_group_missing: DefaultValueIfControlGroupMissingConfig = (
        Field(default_factory=DefaultValueIfControlGroupMissingConfig)
    )


class CompareConfigDocument(CompareConfigs):
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
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def object_id_to_str(cls, v: ObjectId | str) -> str:
        if isinstance(v, ObjectId):
            v = str(v)
        return v
