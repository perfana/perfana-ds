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

from pydantic import Field, StrictFloat, StrictInt

from perfana_ds.schemas.base_document import (
    BaseDocument,
    BaseMetricDocument,
)


class MetricStatistics(BaseDocument):
    mean: StrictInt | StrictFloat | None
    median: StrictInt | StrictFloat | None
    min: StrictInt | StrictFloat | None
    max: StrictInt | StrictFloat | None
    std: StrictInt | StrictFloat | None
    last: StrictInt | StrictFloat | None = None
    n: StrictInt
    n_missing: StrictInt = Field(alias="nMissing")
    n_non_zero: StrictInt = Field(alias="nNonZero")
    q10: StrictInt | StrictFloat | None
    q25: StrictInt | StrictFloat | None
    q75: StrictInt | StrictFloat | None
    q90: StrictInt | StrictFloat | None
    q95: StrictInt | StrictFloat | None = None
    q99: StrictInt | StrictFloat | None = None
    is_constant: bool = Field(alias="isConstant")
    all_missing: bool = Field(alias="allMissing")
    pct_missing: StrictFloat | None = Field(alias="pctMissing", default=None)
    iqr: StrictFloat | StrictInt | None
    idr: StrictFloat | StrictInt | None
    unit: str | None = None
    benchmark_ids: list[str] | None = Field(alias="benchmarkIds", default=None)
    updated_at: datetime = Field(alias="updatedAt")
    isArtificial: bool = False


class MetricStatisticsDocument(BaseMetricDocument, MetricStatistics):
    test_run_start: datetime = Field(alias="testRunStart")
    panel_title: str = Field(alias="panelTitle")
    dashboard_label: str = Field(alias="dashboardLabel")
    dashboard_uid: str = Field(alias="dashboardUid")
    metric_name: str = Field(alias="metricName")
    application_dashboard_id: str = Field(alias="applicationDashboardId")
    panel_id: int = Field(alias="panelId")
    isArtificial: bool = False
