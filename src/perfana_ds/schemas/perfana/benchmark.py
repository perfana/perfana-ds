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

from pydantic import BaseModel, ConfigDict, Field

from .enums import BenchmarkOperator, RequirementOperator


class Requirement(BaseModel):
    operator: RequirementOperator
    value: float

    def evaluate(self, input_value: float) -> bool:
        """Evaluate the requirement against the input value."""
        if self.operator == RequirementOperator.LT:
            return input_value < self.value
        elif self.operator == RequirementOperator.GT:
            return input_value > self.value
        return False


class CompareBenchmark(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    operator: BenchmarkOperator
    value: float
    absolute_failure_threshold: float = Field(0.0, alias="absoluteFailureThreshold")

    def _delta(self, baseline: float, current: float) -> float:
        """Calculate delta (current - baseline)."""
        return current - baseline

    def _percentage(self, baseline: float, current: float) -> float:
        """Calculate percentage change."""
        if baseline == 0.0:
            return 0.0 if current == 0.0 else float("inf")
        return ((current - baseline) / baseline) * 100.0

    def _has_allowed_positive_percentage_outside_absolute_threshold(
        self, baseline: float, current: float
    ) -> bool:
        """Check if positive percentage deviation is within threshold."""
        delta = self._delta(baseline, current)
        if baseline == 0.0:
            return current == 0.0 or delta <= self.absolute_failure_threshold
        return (
            delta <= self.absolute_failure_threshold
            or self._percentage(baseline, current) <= self.value
        )

    def _has_allowed_negative_percentage_outside_absolute_threshold(
        self, baseline: float, current: float
    ) -> bool:
        """Check if negative percentage deviation is within threshold."""
        abs_threshold = abs(self.absolute_failure_threshold)
        delta = self._delta(baseline, current)
        if baseline == 0.0:
            return current == 0.0 or delta <= self.absolute_failure_threshold
        return (delta < 0 and abs(delta) <= abs_threshold) or -self._percentage(
            baseline, current
        ) <= self.value

    def _has_allowed_positive_delta(self, baseline: float, current: float) -> bool:
        """Check if positive delta is within threshold."""
        return self._delta(baseline, current) <= self.value

    def _has_allowed_negative_delta(self, baseline: float, current: float) -> bool:
        """Check if negative delta is within threshold."""
        return -self._delta(baseline, current) <= self.value

    def evaluate(self, baseline: float, current: float) -> bool:
        """Evaluate the benchmark against baseline and current values."""
        if self.operator == BenchmarkOperator.PSTPCT:
            return self._has_allowed_positive_percentage_outside_absolute_threshold(
                baseline, current
            )
        elif self.operator == BenchmarkOperator.NGTPCT:
            return self._has_allowed_negative_percentage_outside_absolute_threshold(
                baseline, current
            )
        elif self.operator == BenchmarkOperator.PST:
            return self._has_allowed_positive_delta(baseline, current)
        elif self.operator == BenchmarkOperator.NGT:
            return self._has_allowed_negative_delta(baseline, current)
        return False
