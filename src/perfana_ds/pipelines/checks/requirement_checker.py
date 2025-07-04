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

"""Service for checking requirements against aggregated metric data."""

import re
from datetime import datetime
from typing import Any

from perfana_ds.catalog.catalog import Catalog
from perfana_ds.schemas.perfana.benchmark import CompareBenchmark, Requirement
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.check_results import CheckResults, CheckResultTarget
from perfana_ds.schemas.perfana.enums import (
    AggregationType,
    BenchmarkOperator,
    PanelType,
    RequirementOperator,
    ResultStatus,
)
from perfana_ds.schemas.perfana.test_runs import TestRun

from .base import BaseCheckService, RequirementCheckError


class RequirementChecker(BaseCheckService):
    """Service to check requirements against aggregated metric data."""

    def __init__(self, catalog: Catalog):
        super().__init__()
        self.catalog = catalog

    def create_check_result(
        self,
        test_run: TestRun,
        benchmark: Benchmark,
        aggregation_result: dict[str, Any],
        grafana_info: str | None = None,
        snapshot_id: str | None = None,
    ) -> CheckResults:
        """Create a CheckResult document from aggregated data.

        Args:
            test_run: The test run being processed
            benchmark: The benchmark configuration
            aggregation_result: Results from data aggregation
            grafana_info: Optional Grafana information
            snapshot_id: Optional snapshot ID

        Returns:
            CheckResults document ready for database insertion

        Raises:
            RequirementCheckError: If check result creation fails
        """
        try:
            # If no requirement config, do not create a CheckResults
            requirement_field = getattr(benchmark.panel, "requirement", None)
            if not requirement_field or (
                getattr(requirement_field, "operator", None) is None
                and getattr(requirement_field, "value", None) is None
            ):
                self.logger.info(
                    f"No requirement config for panel {benchmark.panel.id}, skipping CheckResults creation."
                )
                return None

            # self.logger.info(
            #     f"Creating check result for benchmark {benchmark.id} "
            #     f"on test run {test_run.testRunId}"
            # )

            # Prepare regex for matchPattern if set
            match_pattern = getattr(benchmark.panel, "matchPattern", None)
            regex = None
            if match_pattern:
                try:
                    regex = re.compile(match_pattern)
                except re.error:
                    self.logger.warning(f"Invalid matchPattern regex: {match_pattern}")
                    regex = None
            # Process targets and check requirements
            target_results = []
            overall_meets_requirement = True
            for target_data in aggregation_result.get("targets", []):
                is_artificial = target_data.get("isArtificial", False)
                target_name = target_data.get("target", "")
                # If matchPattern is set and does not match, set meetsRequirement=None
                if regex and not regex.search(target_name):
                    target_result = self._create_target_result(target_data, benchmark)
                    target_result.meetsRequirement = None
                else:
                    target_result = self._create_target_result(target_data, benchmark)
                if is_artificial:
                    target_result.isArtificial = True
                target_results.append(target_result)
                # Update overall requirement status
                if target_result.meetsRequirement is False:
                    overall_meets_requirement = False

            # Check panel average requirement if available
            panel_average = aggregation_result.get("panel_average")
            panel_meets_requirement = None

            if panel_average is not None and benchmark.panel.requirement:
                panel_meets_requirement = self._check_requirement(
                    float(panel_average), benchmark.panel.requirement
                )
                if panel_meets_requirement is False:
                    overall_meets_requirement = False

            # Determine final status
            status = ResultStatus.COMPLETE
            message = self._generate_status_message(
                overall_meets_requirement, len(target_results), aggregation_result
            )

            # Debug logging for panelType mapping
            panel_type_input = benchmark.panel.type
            mapped_panel_type = (
                PanelType.from_original_name(panel_type_input)
                if panel_type_input
                else None
            )
            # print(f"[CheckResults] benchmark.panel.type='{panel_type_input}', mapped_panel_type='{mapped_panel_type}'")
            # Create CheckResults document
            check_result = CheckResults(
                application=test_run.application,
                testEnvironment=test_run.testEnvironment,
                testType=test_run.testType,
                testRunId=test_run.testRunId,
                grafana=grafana_info or "",
                dashboardLabel=benchmark.dashboardLabel,
                dashboardUid=benchmark.dashboardUid,
                panelTitle=self._strip_panel_title_prefix(benchmark.panel.title),
                panelId=benchmark.panel.id,
                panelType=mapped_panel_type or PanelType.GRAPH,
                panelDescription=getattr(benchmark.panel, "description", None),
                panelYAxesFormat=getattr(benchmark.panel, "yAxesFormat", None),
                genericCheckId=benchmark.genericCheckId,
                benchmarkId=benchmark.id,
                snapshotId=snapshot_id or "",
                snapshotKey=None,
                snapshotPanelUrl=None,
                status=status,
                message=message,
                detailedMessage=None,
                checkDurationMs=None,
                excludeRampUpTime=benchmark.excludeRampUpTime,
                rampUp=getattr(test_run, "rampUp", 0),
                averageAll=benchmark.averageAll or False,
                evaluateType=AggregationType.from_original_name(
                    benchmark.panel.evaluateType
                )
                or AggregationType.MEAN,
                matchPattern=match_pattern,
                titleReplacer=None,
                panelAverage=panel_average,
                meetsRequirement=overall_meets_requirement if target_results else None,
                requirement=self._convert_requirement(benchmark.panel.requirement),
                benchmark=self._convert_benchmark(benchmark.panel.benchmark),
                validateWithDefaultIfNoData=benchmark.validateWithDefaultIfNoData
                or False,
                validateWithDefaultIfNoDataValue=benchmark.validateWithDefaultIfNoDataValue
                or 0.0,
                targets=target_results,
                perfanaInfo=f"Created by Perfana Check Pipeline at {datetime.now().isoformat()}",
            )

            return check_result

        except Exception as e:
            raise RequirementCheckError(f"Failed to create check result: {str(e)}")

    def _create_target_result(
        self, target_data: dict[str, Any], benchmark: Benchmark
    ) -> CheckResultTarget:
        """Create a CheckResultTarget from target aggregation data."""
        target_name = target_data.get("target", "")
        target_value = target_data.get("value")

        meets_requirement = None
        if target_value is not None and benchmark.panel.requirement:
            meets_requirement = self._check_requirement(
                float(target_value), benchmark.panel.requirement
            )

        return CheckResultTarget(
            target=target_name,
            value=target_value,
            meetsRequirement=meets_requirement,
            isArtificial=False,  # Could be enhanced to detect artificial data
            fitPercentageChange=None,  # Could be implemented for FIT aggregation
            fitAbsoluteChange=None,
            fitQuality=None,
            fitMeetsRequirement=None,
        )

    def _check_requirement(self, value: float, requirement_config) -> bool:
        """Check if a value meets the requirement."""
        if not requirement_config:
            return True

        # Handle both Pydantic objects and dictionaries
        if hasattr(requirement_config, "operator") and hasattr(
            requirement_config, "value"
        ):
            # Pydantic BenchmarkRequirement object
            operator = requirement_config.operator
            threshold = requirement_config.value
        else:
            # Dictionary
            operator = requirement_config.get("operator")
            threshold = requirement_config.get("value")

        if operator is None or threshold is None:
            return True

        # Handle operator as enum or string
        operator_str = (
            operator.value if hasattr(operator, "value") else str(operator).lower()
        )

        if operator_str == "lt":
            return value < threshold
        elif operator_str == "gt":
            return value > threshold
        else:
            self.logger.warning(f"Unknown requirement operator: {operator_str}")
            return True

    def _convert_requirement(self, requirement_config) -> Requirement | None:
        """Convert benchmark requirement config to Requirement object."""
        if not requirement_config:
            return None

        # Handle both Pydantic objects and dictionaries
        if hasattr(requirement_config, "operator") and hasattr(
            requirement_config, "value"
        ):
            # Already a Pydantic Requirement object or BenchmarkRequirement
            operator = requirement_config.operator
            value = requirement_config.value
        else:
            # Dictionary
            operator = requirement_config.get("operator")
            value = requirement_config.get("value")

        if not operator or value is None:
            return None

        try:
            # Handle operator as enum or string
            if hasattr(operator, "value"):
                operator_enum = RequirementOperator(operator.value)
            else:
                operator_enum = RequirementOperator(operator)

            return Requirement(operator=operator_enum, value=float(value))
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to convert requirement: {e}")
            return None

    def _convert_benchmark(self, benchmark_config) -> CompareBenchmark | None:
        """Convert benchmark config to CompareBenchmark object."""
        if not benchmark_config:
            return None

        # Handle both Pydantic objects and dictionaries
        if hasattr(benchmark_config, "operator") and hasattr(benchmark_config, "value"):
            # Already a Pydantic CompareBenchmark or BenchmarkComparison object
            operator = benchmark_config.operator
            value = benchmark_config.value
            absolute_failure_threshold = getattr(
                benchmark_config, "absolute_failure_threshold", 0.0
            )
        else:
            # Dictionary
            operator = benchmark_config.get("operator")
            value = benchmark_config.get("value")
            absolute_failure_threshold = benchmark_config.get(
                "absoluteFailureThreshold", 0.0
            )

        if not operator or value is None:
            return None

        try:
            # Handle operator as enum or string
            if hasattr(operator, "value"):
                operator_enum = BenchmarkOperator(operator.value)
            else:
                operator_enum = BenchmarkOperator(operator)

            return CompareBenchmark(
                operator=operator_enum,
                value=float(value),
                absolute_failure_threshold=float(absolute_failure_threshold),
            )
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to convert benchmark: {e}")
            return None

    def _generate_status_message(
        self,
        meets_requirement: bool,
        target_count: int,
        aggregation_result: dict[str, Any],
    ) -> str:
        """Generate a status message for the check result."""
        if target_count == 0:
            return "No targets found for processing"

        if meets_requirement:
            return f"All {target_count} targets meet requirements"
        else:
            failed_count = sum(
                1
                for target in aggregation_result.get("targets", [])
                if target.get("meets_requirement") is False
            )
            return f"{failed_count} of {target_count} targets failed requirements"

    def _strip_panel_title_prefix(self, title: str) -> str:
        if not title:
            return title
        if "-" in title:
            return title.split("-", 1)[1].strip()
        return title

    def process(
        self,
        test_run: TestRun,
        benchmark: Benchmark,
        aggregation_result: dict[str, Any],
        **kwargs,
    ) -> CheckResults:
        """Process method implementation for BaseCheckService."""
        return self.create_check_result(
            test_run, benchmark, aggregation_result, **kwargs
        )
