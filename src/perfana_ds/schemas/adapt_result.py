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
from pydantic import ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from perfana_ds.schemas.base_document import BaseDocument, BaseMetricDocument
from perfana_ds.schemas.compare_config import CompareConfigs
from perfana_ds.schemas.metric_comparison import (
    NumericDifferenceRecord,
    NumericDifferenceRecordWithIqr,
)


class ConclusionResult(BaseDocument):
    class ConclusionDetails(BaseDocument):
        model_config = ConfigDict(
            alias_generator=to_camel, populate_by_name=True, extra="allow"
        )
        message: str

    valid: bool
    label: Literal[
        "no difference",
        "increase",
        "decrease",
        "partial increase",
        "partial decrease",
        "incomparable",
        "regression",
        "improvement",
        "partial regression",
        "partial improvement",
    ]
    partial_difference: bool
    all_difference: bool
    increase: bool
    decrease: bool
    ignore: bool
    # detail: dict[str, Any]


class CompareScore(BaseDocument):
    idr: float | None
    iqr: float | None
    overall: int | None


class CompareCheckResult(BaseDocument):
    valid: bool
    invalid_reasons: list[str]
    observed_diff: float | None
    increase: bool | None
    decrease: bool | None
    is_difference: bool | None
    # strength: float | None


class CompareCheckResults(BaseDocument):
    pct: CompareCheckResult
    iqr: CompareCheckResult
    abs: CompareCheckResult
    constant: CompareCheckResult


class CompareThresholdResults(BaseDocument):
    class ThresholdBounds(BaseDocument):
        pct: float | None
        iqr: float | None
        abs: float | None
        constant: float | None
        overall: float | None

    upper: ThresholdBounds
    lower: ThresholdBounds


class ConditionsResults(BaseDocument):
    enough_observations: bool
    not_all_missing: bool
    control_not_constant: bool | None
    control_constant: bool | None
    control_not_zero: bool
    control_exists: bool
    has_abs_check: bool
    iqr_not_zero: bool


class CompareOverallCheckResult(BaseDocument):
    valid: bool


class CompareResultStatistic(NumericDifferenceRecord):
    name: str


class CompareResultStatisticWithIQR(NumericDifferenceRecordWithIqr):
    name: str


class MetricClassificationSubset(BaseDocument):
    metric_classification: str | None
    higher_is_better: bool | None


class BaseCompareResultDocument(BaseMetricDocument):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        arbitrary_types_allowed=True,
    )
    panel_title: str
    dashboard_label: str
    dashboard_uid: str
    thresholds: CompareThresholdResults
    conditions: ConditionsResults
    checks: CompareCheckResults
    conclusion: ConclusionResult
    # score: CompareScore
    statistic: CompareResultStatisticWithIQR | CompareResultStatistic
    compare_config: CompareConfigs
    metric_classification: MetricClassificationSubset
    unit: str | None = None


class AdaptResultDocument(BaseCompareResultDocument):
    control_group_id: str
    test_run_start: datetime


class CompareRunResultDocument(BaseCompareResultDocument):
    compare_run_id: str


class AdaptTrackedResultDocument(AdaptResultDocument):
    tracked_conclusion: ConclusionResult
    tracked_difference_id: ObjectId

    @field_validator("tracked_difference_id", mode="before")
    @classmethod
    def str_to_object_id(cls, v) -> ObjectId | None:
        if isinstance(v, str):
            v = ObjectId(v)
        return v
