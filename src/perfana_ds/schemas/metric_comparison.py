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

from pydantic import StrictFloat, StrictInt
from pydantic.json_schema import GenerateJsonSchema

from perfana_ds.schemas.base_document import (
    BaseDocument,
    BaseMetricDocument,
)

GenerateJsonSchema


class BoolCompare(BaseDocument):
    test: bool | None
    control: bool | None = None


class StrCompare(BaseDocument):
    test: str | None = None
    control: str | None = None


class NumericDifferenceRecord(BaseDocument):
    test: StrictInt | StrictFloat | None
    control: StrictInt | StrictFloat | None = None
    diff: StrictInt | StrictFloat | None
    pct_diff: StrictFloat | None


class NumericDifferenceRecordWithIqr(BaseDocument):
    test: StrictInt | StrictFloat | None
    control: StrictInt | StrictFloat | None = None
    diff: StrictInt | StrictFloat | None
    abs_diff: StrictInt | StrictFloat | None
    pct_diff: StrictFloat | None
    iqr_diff: StrictFloat | None


class Quantiles(BaseDocument):
    q10: NumericDifferenceRecordWithIqr
    q25: NumericDifferenceRecordWithIqr
    q75: NumericDifferenceRecordWithIqr
    q90: NumericDifferenceRecordWithIqr


class CountAndPct(BaseDocument):
    count: int | None
    pct: float | None


class MetricCompareStatistics(BaseDocument):
    class Outliers(BaseDocument):
        medium: CountAndPct
        extreme: CountAndPct

    class InRange(BaseDocument):
        iqr: CountAndPct
        idr: CountAndPct
        minmax: CountAndPct

    class LTorGT(BaseDocument):
        iqr: CountAndPct
        idr: CountAndPct
        min: CountAndPct
        max: CountAndPct

    # outliers: Outliers
    in_range: InRange
    outside_range: InRange
    lt: LTorGT
    gt: LTorGT


class MetricStatisticsDifference(BaseDocument):
    exists: BoolCompare
    is_constant: BoolCompare
    all_missing: BoolCompare
    mean: NumericDifferenceRecordWithIqr
    median: NumericDifferenceRecordWithIqr
    min: NumericDifferenceRecordWithIqr
    max: NumericDifferenceRecordWithIqr
    iqr: NumericDifferenceRecord
    idr: NumericDifferenceRecord
    std: NumericDifferenceRecord
    n: NumericDifferenceRecord
    pct_missing: NumericDifferenceRecord
    n_missing: NumericDifferenceRecord
    n_non_zero: NumericDifferenceRecord
    q10: NumericDifferenceRecord
    q25: NumericDifferenceRecord
    q75: NumericDifferenceRecord
    q90: NumericDifferenceRecord
    # metric: MetricCompareStatistics


class ControlGroupComparisonDocument(BaseMetricDocument, MetricStatisticsDifference):
    control_group_id: str
    panel_title: str
    dashboard_label: str
    dashboard_uid: str
    unit: str | None = None


class RunComparisonDocument(BaseMetricDocument, MetricStatisticsDifference):
    compare_run_id: str
    panel_title: str
    dashboard_label: str
    dashboard_uid: str
    unit: str | None = None
