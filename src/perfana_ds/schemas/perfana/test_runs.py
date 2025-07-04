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

"""Schema for sestRuns.

Reference: https://github.com/perfana/perfana-fe/blob/main/imports/collections/testruns.js

TODO: Why are all field optional?
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, Json

from perfana_ds.schemas.base_extra import BaseModelExtra


class EvaluateStatus(str, Enum):
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    RE_EVALUATE = "RE_EVALUATE"
    RE_EVALUATE_ADAPT = "RE_EVALUATE_ADAPT"
    REFRESH = "REFRESH"
    BATCH_PROCESSING = "BATCH_PROCESSING"
    NO_BASELINES_FOUND = "NO_BASELINES_FOUND"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NO_DASHBOARDS_FOUND = "NO_DASHBOARDS_FOUND"
    NO_AUTO_COMPARE = "NO_AUTO_COMPARE"
    BASELINE_TEST_RUN = "BASELINE_TEST_RUN"


class DifferencesAccepted(str, Enum):
    TBD = "TBD"
    ACCEPTED = "ACCEPTED"
    DENIED = "DENIED"


class ReportAnnotationPanel(BaseModelExtra):
    title: str | None = None
    id: int = 0
    annotation: str | None = None


class ReportAnnotation(BaseModelExtra):
    application: str | None = None
    testType: str | None = None
    testEnvironment: str | None = None
    grafana: str | None = None
    dashboardLabel: str | None = None
    dashboardUid: str | None = None
    index: int = 0
    panel: ReportAnnotationPanel | None = None


class TestRunVariable(BaseModelExtra):
    placeholder: str
    value: str


class Adapt(BaseModelExtra):
    mode: str
    differencesAccepted: DifferencesAccepted


class TestRunStatus(BaseModelExtra):
    creatingSnapshots: EvaluateStatus = EvaluateStatus.STARTED
    evaluatingChecks: EvaluateStatus = EvaluateStatus.STARTED
    evaluatingComparisons: EvaluateStatus = EvaluateStatus.STARTED
    evaluatingAdapt: EvaluateStatus = EvaluateStatus.STARTED
    lastUpdate: datetime | None = None


class ConsolidatedResult(BaseModelExtra):
    meetsRequirement: bool = True
    benchmarkPreviousTestRunOK: bool = True
    benchmarkBaselineTestRunOK: bool = True
    adaptTestRunOK: bool = True
    overall: bool = True


class TestRun(BaseModelExtra):
    id: str = Field(alias="_id")
    version: int | str | None = None
    testRunId: str
    ciBuildResultsUrl: str | None = None
    abort: bool = False
    alerts: list[str] = Field(default_factory=list)
    annotations: str | None = None
    application: str
    applicationRelease: str | None = None
    completed: bool = False
    duration: int = 0
    start: datetime | None = None
    end: datetime | None = None
    expired: bool = False
    expires: int = 0
    plannedDuration: int = 0
    rampUp: int = 0
    reasonsNotValid: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    testEnvironment: str
    testType: str
    valid: bool = False
    variables: list[TestRunVariable] = Field(default_factory=list)
    viewedBy: list[str] = Field(default_factory=list)
    consolidatedResult: ConsolidatedResult | None = None
    reportAnnotations: list[ReportAnnotation] = Field(default_factory=list)
    status: TestRunStatus | None = None
    adapt: Adapt | None = None
    # legacy fields for backward compatibility
    CIBuildResultsUrl: str | None = None
    abortMessage: str | None = None
    alerts_legacy: list[dict[str, Any] | Json] = Field(default_factory=list)
    events: list[dict[str, Any] | Json] = Field(default_factory=list)
    # adapt_baseline_mode_enabled is deprecated, use adapt instead
    adapt_baseline_mode_enabled: bool = False
