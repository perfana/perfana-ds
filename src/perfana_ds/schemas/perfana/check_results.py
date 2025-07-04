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

from datetime import timedelta

from pydantic import BaseModel

from perfana_ds.schemas.base_extra import BaseModelExtra

from .benchmark import CompareBenchmark, Requirement
from .enums import AggregationType, PanelType, ResultStatus


class CheckResultTarget(BaseModel):
    target: str = ""
    value: float | None = None
    meetsRequirement: bool | None = None
    isArtificial: bool | None = False
    fitPercentageChange: float | None = None
    fitAbsoluteChange: float | None = None
    fitQuality: float | None = None
    fitMeetsRequirement: bool | None = None


class CheckResults(BaseModelExtra):
    application: str
    testEnvironment: str
    testType: str
    testRunId: str
    grafana: str
    dashboardLabel: str | None = None
    dashboardUid: str
    panelTitle: str
    panelId: int
    panelType: PanelType = PanelType.GRAPH
    panelDescription: str | None = None
    panelYAxesFormat: str | None = None
    genericCheckId: str | None = None
    benchmarkId: str
    snapshotId: str
    snapshotKey: str | None = None
    snapshotPanelUrl: str | None = None
    status: ResultStatus = ResultStatus.NEW
    message: str | None = None
    detailedMessage: str | None = None
    checkDurationMs: int | None = None
    excludeRampUpTime: bool = True
    rampUp: int = 0
    averageAll: bool = False
    evaluateType: AggregationType
    matchPattern: str | None = None
    titleReplacer: str | None = None
    panelAverage: float | None = None
    meetsRequirement: bool | None = None
    requirement: Requirement | None = None
    benchmark: CompareBenchmark | None = None
    validateWithDefaultIfNoData: bool = False
    validateWithDefaultIfNoDataValue: float = 0.0
    targets: list[CheckResultTarget] | None = []
    perfanaInfo: str | None = None

    def regexp_matches_target(self, target_name: str) -> bool:
        """Check if target name matches the match pattern."""
        if self.matchPattern is None:
            return True
        import re

        try:
            pattern = re.compile(self.matchPattern)
            return pattern.search(target_name) is not None
        except re.error:
            return True

    def duration_to_skip_based_on_exclude_ramp_up(self) -> timedelta:
        """Get duration to skip based on exclude ramp up setting."""
        if self.excludeRampUpTime:
            return timedelta(seconds=self.rampUp)
        return timedelta(0)
