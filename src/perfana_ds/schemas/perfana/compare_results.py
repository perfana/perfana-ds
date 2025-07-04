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
from typing import ClassVar

from pydantic import Field

from perfana_ds.schemas.base_extra import BaseModelExtra

from .benchmark import CompareBenchmark
from .enums import AggregationType, PanelType, ResultStatus


class CompareResultTarget(BaseModelExtra):
    target: str = ""
    rawBaselineValue: float | None = None
    rawCurrentValue: float | None = None
    rawDelta: float | None = None
    rawDeltaPct: float | None = None
    baselineValue: float | None = Field(
        alias="benchmarkBaselineTestRunValue", default=None
    )
    currentValue: float | None = Field(alias="value", default=None)
    delta: float | None = Field(alias="benchmarkBaselineTestRunDelta", default=None)
    deltaPct: float | None = Field(
        alias="benchmarkBaselineTestRunDeltaPct", default=None
    )
    meetsRequirement: bool | None = Field(
        alias="benchmarkBaselineTestRunOK", default=None
    )
    isBaselineArtificial: bool | None = False
    isCurrentArtificial: bool | None = False

    @classmethod
    def build(
        cls,
        target_name: str,
        baseline: float,
        current: float,
        target_requirement: bool | None,
        is_baseline_artificial: bool,
        is_current_artificial: bool,
    ) -> "CompareResultTarget":
        """Build a CompareResultTarget from baseline and current values."""
        delta = current - baseline

        # Calculate percentage, handling division by zero
        if baseline == 0.0:
            delta_pct = 0.0 if current == 0.0 else float("inf")
        else:
            delta_pct = (delta / baseline) * 100.0

        return cls(
            target=target_name,
            rawBaselineValue=baseline,
            rawCurrentValue=current,
            rawDelta=delta,
            rawDeltaPct=delta_pct if delta_pct != float("inf") else None,
            baselineValue=float(baseline),
            currentValue=float(current),
            delta=float(delta),
            deltaPct=float(delta_pct) if delta_pct != float("inf") else None,
            meetsRequirement=target_requirement,
            isBaselineArtificial=is_baseline_artificial,
            isCurrentArtificial=is_current_artificial,
        )


class CompareResults(BaseModelExtra):
    application: str
    testEnvironment: str
    testType: str
    grafana: str
    testRunId: str
    dashboardLabel: str
    dashboardUid: str
    baselineTestRunId: str
    currentSnapshotId: str | None = Field(alias="snapshotId", default=None)
    currentSnapshotKey: str | None = Field(alias="snapshotKey", default=None)
    baselineSnapshotId: str | None = Field(
        alias="baselineTestRunSnapshotId", default=None
    )
    baselineSnapshotKey: str | None = Field(
        alias="baselineTestRunSnapshotKey", default=None
    )
    snapshotPanelUrl: str | None = None
    baselineSnapshotPanelUrl: str | None = None
    panelTitle: str
    panelId: int
    panelType: PanelType = PanelType.GRAPH
    panelDescription: str | None = None
    panelYAxesFormat: str | None = None
    genericCheckId: str | None = None
    benchmarkId: str | None = None
    status: ResultStatus = ResultStatus.NEW
    message: str | None = None
    detailedMessage: str | None = None
    checkDurationMs: int | None = None
    excludeRampUpTime: bool = True
    rampUp: int = 0
    label: str | None = None
    averageAll: bool = False
    evaluateType: AggregationType
    matchPattern: str | None = None
    titleReplacer: str | None = None
    benchmark: CompareBenchmark | None = None
    currentPanelAverage: float | None = Field(alias="panelAverage", default=None)
    baselinePanelAverage: float | None = Field(
        alias="benchmarkBaselineTestRunPanelAverage", default=None
    )
    panelAverageDelta: float | None = Field(
        alias="benchmarkBaselineTestRunPanelAverageDelta", default=None
    )
    panelAverageDeltaPct: float | None = Field(
        alias="benchmarkBaselineTestRunPanelAverageDeltaPct", default=None
    )
    meetsRequirement: bool | None = Field(
        alias="benchmarkBaselineTestRunOK", default=None
    )
    targets: list[CompareResultTarget] | None = []
    validateWithDefaultIfNoData: bool = False
    validateWithDefaultIfNoDataValue: float = 0.0
    perfanaInfo: str | None = None
    adHoc: bool | None = None

    # Constants for auto-compare labels
    LABEL_AUTO_COMPARE_BASELINE_PREFIX: ClassVar[str] = "Compared to fixed baseline"
    LABEL_AUTO_COMPARE_PREVIOUS_PREFIX: ClassVar[str] = "Compared to previous test run"

    def human_readable_summary(self) -> str:
        """Generate a human-readable summary of the compare result."""
        return f"CompareResult: {self.application} - {self.dashboardLabel} - {self.panelTitle}"

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

    def is_created_by_auto_compare_baseline(self) -> bool:
        """Check if this result was created by auto-compare baseline."""
        return self.label is not None and self.label.startswith(
            self.LABEL_AUTO_COMPARE_BASELINE_PREFIX
        )

    def is_created_by_auto_compare_previous(self) -> bool:
        """Check if this result was created by auto-compare previous."""
        return self.label is not None and self.label.startswith(
            self.LABEL_AUTO_COMPARE_PREVIOUS_PREFIX
        )

    def is_created_manually(self) -> bool:
        """Check if this result was created manually."""
        return (
            not self.is_created_by_auto_compare_previous()
            and not self.is_created_by_auto_compare_baseline()
        )
