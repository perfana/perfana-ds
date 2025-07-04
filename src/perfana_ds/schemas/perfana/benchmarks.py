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

"""Schema for applications collection.

Reference: https://github.com/perfana/perfana-fe/blob/main/imports/collections/benchmarks.js
"""

from typing import Literal

from pydantic import BaseModel, Field

from perfana_ds.schemas.base_extra import BaseModelExtra

OPERATORS = Literal["eq", "ne", "lt", "gt", "pst", "ngt", "pst-pct", "ngt-pct"]


class BenchmarkPanel(BaseModelExtra):
    class BenchmarkRequirement(BaseModel):
        operator: OPERATORS | None = None
        value: float | None = None

    class BenchmarkField(BaseModel):
        operator: OPERATORS | None = None
        value: float | None = None
        absoluteFailureThreshold: float | None = None

    id: int
    title: str
    type: str
    yAxesFormat: str | None = None
    evaluateType: Literal["avg", "max", "min", "last", "fit", "mean"]
    requirement: BenchmarkRequirement = Field(default_factory=BenchmarkRequirement)
    benchmark: BenchmarkField = Field(default_factory=BenchmarkField)


class Benchmark(BaseModelExtra):
    id: str = Field(alias="_id")
    application: str
    testType: str
    testEnvironment: str
    grafana: str
    dashboardLabel: str
    dashboardId: int
    dashboardUid: str
    panel: BenchmarkPanel
    genericCheckId: str | None = None
    valid: bool | None = None
    reasonNotValid: str | None = None
    excludeRampUpTime: bool = True
    averageAll: bool | None = None
    matchPattern: str | None = None
    validateWithDefaultIfNoData: bool | None = None
    validateWithDefaultIfNoDataValue: float | None = None
    updateTestRuns: bool | None = None
