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

"""
Enhanced benchmark comparison logic for comparing test results against baselines.
Based on Kotlin implementation in perfana-check/compareresult.
"""

import re
from datetime import datetime
from typing import Any

from perfana_ds.catalog.catalog import Catalog
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.check_results import CheckResults
from perfana_ds.schemas.perfana.compare_results import (
    CompareResults,
    CompareResultTarget,
)
from perfana_ds.schemas.perfana.enums import (
    AggregationType,
    BenchmarkOperator,
    PanelType,
    ResultStatus,
)
from perfana_ds.schemas.perfana.test_runs import TestRun

from .base import BaseCheckService


class BenchmarkComparator(BaseCheckService):
    """Service for comparing test results against baseline benchmarks using dsMetricStatistics only."""

    def __init__(self, catalog: Catalog):
        super().__init__()
        self.catalog = catalog
        self.default_baseline_days = 30
        self.minimum_baseline_samples = 3

    def process(
        self, test_run: TestRun, benchmarks: list[Benchmark]
    ) -> list[CompareResults]:
        """Process benchmarks and create compare results by comparing dsMetricStatistics for testRun and baseline/previous test run."""
        compare_results = []
        for benchmark in benchmarks:
            # Previous test run comparison
            prev_result = self.create_compare_result_previous(test_run, benchmark)
            if prev_result:
                compare_results.append(prev_result)
            # Fixed baseline comparison
            baseline_result = self.create_compare_result_baseline(test_run, benchmark)
            if baseline_result:
                compare_results.append(baseline_result)
        return compare_results

    def create_compare_result_previous(
        self, test_run: TestRun, benchmark: Benchmark
    ) -> CompareResults | None:
        previous_test_run = self._find_previous_test_run(test_run)
        if not previous_test_run:
            self.logger.warning(f"No previous test run found for {test_run.testRunId}")
            return None
        return self._create_compare_result_from_stats(
            test_run, previous_test_run, benchmark, label_snippet="previous test run"
        )

    def create_compare_result_baseline(
        self, test_run: TestRun, benchmark: Benchmark
    ) -> CompareResults | None:
        baseline_test_run = self._find_fixed_baseline_test_run(test_run)
        if not baseline_test_run:
            self.logger.warning(
                f"No fixed baseline test run found for {test_run.testRunId}"
            )
            return None
        return self._create_compare_result_from_stats(
            test_run, baseline_test_run, benchmark, label_snippet="fixed baseline"
        )

    def _find_previous_test_run(self, test_run: TestRun) -> TestRun | None:
        """
        Find the previous test run for the given test run.
        The previous test run is the most recent completed test run that is valid.
        """
        try:
            # Query for previous test runs using catalog
            filter_criteria = {
                "application": test_run.application,
                "testEnvironment": test_run.testEnvironment,
                "testType": test_run.testType,
                "completed": True,
                "$or": [
                    {"valid": {"$exists": False}},  # Backwards compatibility
                    {"valid": True},
                ],
            }

            # Sort by end time descending to get most recent first
            previous_runs = self.catalog.testRuns.load_objects(
                filter_criteria,
                sort=[("end", -1)],
                limit=10,  # Limit to avoid loading too many
            )

            if not previous_runs:
                return None

            # Find the first run that ended before current test run
            current_end = getattr(test_run, "end", None)
            for run in previous_runs:
                # Skip if it's the same test run
                if run.testRunId == test_run.testRunId:
                    continue

                run_end = getattr(run, "end", None)
                if run_end and current_end and run_end < current_end:
                    return run
                elif not current_end:  # If current run has no end time, use most recent
                    return run

            return None

        except Exception as e:
            self.logger.error(f"Error finding previous test run: {e}")
            return None

    def _find_fixed_baseline_test_run(self, test_run: TestRun) -> TestRun | None:
        """
        Find the fixed baseline test run for the given test run.
        Baseline test run ID is configured in application settings.
        """
        try:
            # Get application configuration using catalog
            application = self.catalog.applications.load_object(
                {"name": test_run.application}
            )

            if not application:
                self.logger.warning(f"Application not found: {test_run.application}")
                return None

            # Find test environment configuration
            test_env = None
            for env in application.testEnvironments or []:
                if env.name == test_run.testEnvironment:
                    test_env = env
                    break

            if not test_env:
                self.logger.warning(
                    f"Test environment not found: {test_run.testEnvironment}"
                )
                return None

            # Find test type configuration
            test_type_config = None
            for tt in test_env.testTypes or []:
                if tt.name == test_run.testType:
                    test_type_config = tt
                    break

            if not test_type_config:
                self.logger.warning(f"Test type not found: {test_run.testType}")
                return None

            # Get baseline test run ID
            baseline_test_run_id = test_type_config.baselineTestRun
            if not baseline_test_run_id or baseline_test_run_id == test_run.testRunId:
                self.logger.warning(
                    f"No valid baseline test run configured for {test_run.application}/{test_run.testEnvironment}/{test_run.testType}"
                )
                return None

            # Find the baseline test run using catalog
            baseline_test_run = self.catalog.testRuns.load_object(
                {
                    "testRunId": baseline_test_run_id,
                    "application": test_run.application,
                    "testEnvironment": test_run.testEnvironment,
                    "testType": test_run.testType,
                }
            )

            if not baseline_test_run:
                self.logger.warning(
                    f"Baseline test run not found: {baseline_test_run_id}"
                )
                return None

            # Check if baseline test run is before current test run
            baseline_end = getattr(baseline_test_run, "end", None)
            current_end = getattr(test_run, "end", None)

            if baseline_end and current_end and baseline_end >= current_end:
                self.logger.warning(
                    f"Baseline test run is not before current test run: baseline={baseline_end}, current={current_end}"
                )
                return None

            return baseline_test_run

        except Exception as e:
            self.logger.error(f"Error finding fixed baseline test run: {e}")
            return None

    def _get_aggregation_result(
        self, test_run: TestRun, benchmark: Benchmark
    ) -> dict[str, Any]:
        filter_criteria = {
            "testRunId": test_run.testRunId,
            "dashboardUid": benchmark.dashboardUid,
            "dashboardLabel": benchmark.dashboardLabel,
            "panelId": benchmark.panel.id,
        }
        metric_statistics = self.catalog.ds.metricStatistics.load_objects(
            filter_criteria
        )
        if not metric_statistics:
            if getattr(benchmark.panel, "validateWithDefaultIfNoData", False):
                default_value = getattr(
                    benchmark.panel, "validateWithDefaultIfNoDataValue", 0.0
                )
                from datetime import datetime

                from perfana_ds.schemas.metric_statistics import (
                    MetricStatisticsDocument,
                )

                metric_name = getattr(benchmark, "metricName", "default")
                now = datetime.utcnow()
                doc = MetricStatisticsDocument(
                    test_run_id=test_run.testRunId,
                    application_dashboard_id=getattr(
                        benchmark, "applicationDashboardId", ""
                    ),
                    dashboard_uid=benchmark.dashboardUid,
                    panel_id=benchmark.panel.id,
                    panel_title=benchmark.panel.title,
                    dashboard_label=benchmark.dashboardLabel,
                    metric_name=metric_name,
                    mean=default_value,
                    median=default_value,
                    min=default_value,
                    max=default_value,
                    std=0.0,
                    last=default_value,
                    n=1,
                    n_missing=0,
                    n_non_zero=1 if default_value != 0 else 0,
                    q10=default_value,
                    q25=default_value,
                    q75=default_value,
                    q90=default_value,
                    q95=default_value,
                    q99=default_value,
                    is_constant=True,
                    all_missing=False,
                    pct_missing=0.0,
                    iqr=0.0,
                    idr=0.0,
                    unit=None,
                    benchmark_ids=[],
                    updated_at=now,
                    test_run_start=now,
                    isArtificial=True,
                )
                self.catalog.ds.metricStatistics.save_object(doc)
                return {
                    "panel_average": default_value,
                    "targets": [
                        {
                            "target": metric_name,
                            "value": default_value,
                            "isArtificial": True,
                        }
                    ],
                }
            self.logger.warning(
                f"No dsMetricStatistics found for testRunId={test_run.testRunId}, panelId={benchmark.panel.id}"
            )
            return {"panel_average": None, "targets": []}
        evaluate_type = getattr(benchmark.panel, "evaluateType", "mean")
        field_name = self._map_aggregation_type_to_field(
            AggregationType.from_original_name(evaluate_type) or AggregationType.MEAN
        )
        targets = []
        values = []
        for stat in metric_statistics:
            metric_name = getattr(stat, "metric_name", None)
            value = getattr(stat, field_name, None)
            if value is not None and metric_name is not None:
                is_artificial = getattr(stat, "isArtificial", False)
                targets.append(
                    {
                        "target": metric_name,
                        "value": float(value),
                        "isArtificial": is_artificial,
                    }
                )
                values.append(float(value))
        panel_average = None
        if benchmark.averageAll and values:
            panel_average = sum(values) / len(values)
        elif values:
            panel_average = values[0]
        return {"panel_average": panel_average, "targets": targets}

    def _get_aggregation_result_with_smart_backfill(
        self,
        test_run: TestRun,
        benchmark: Benchmark,
        current_targets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Get aggregation result with smart backfilling that uses current test run's target names.
        If baseline has no data but validateWithDefaultIfNoData is True, create artificial
        dsMetricStatistics using the same target names as the current test run.
        """
        # Get target names from current test run to search for matching dsMetricStatistics
        current_target_names = (
            [target["target"] for target in current_targets] if current_targets else []
        )

        if current_target_names:
            # Look for dsMetricStatistics that match the current target names
            filter_criteria = {
                "testRunId": test_run.testRunId,
                "dashboardUid": benchmark.dashboardUid,
                "dashboardLabel": benchmark.dashboardLabel,
                "panelId": benchmark.panel.id,
                "metricName": {
                    "$in": current_target_names
                },  # Only find matching metric names
            }
        else:
            # Fallback to original filter if no current targets
            filter_criteria = {
                "testRunId": test_run.testRunId,
                "dashboardUid": benchmark.dashboardUid,
                "dashboardLabel": benchmark.dashboardLabel,
                "panelId": benchmark.panel.id,
            }

        metric_statistics = self.catalog.ds.metricStatistics.load_objects(
            filter_criteria
        )

        # Check if we have all the required metric statistics for current targets
        existing_metric_names = (
            {stat.metric_name for stat in metric_statistics}
            if metric_statistics
            else set()
        )
        missing_metric_names = set(current_target_names) - existing_metric_names

        if missing_metric_names and getattr(
            benchmark.panel, "validateWithDefaultIfNoData", False
        ):
            # Smart backfilling for missing metric names
            default_value = getattr(
                benchmark.panel, "validateWithDefaultIfNoDataValue", 0.0
            )
            from datetime import datetime

            from perfana_ds.schemas.metric_statistics import MetricStatisticsDocument

            self.logger.info(
                f"Smart backfilling dsMetricStatistics for {test_run.testRunId} missing target names: {missing_metric_names}"
            )

            now = datetime.utcnow()

            # Create artificial dsMetricStatistics for missing target names
            for target_name in missing_metric_names:
                doc = MetricStatisticsDocument(
                    test_run_id=test_run.testRunId,
                    application_dashboard_id=getattr(
                        benchmark, "applicationDashboardId", ""
                    ),
                    dashboard_uid=benchmark.dashboardUid,
                    panel_id=benchmark.panel.id,
                    panel_title=benchmark.panel.title,
                    dashboard_label=benchmark.dashboardLabel,
                    metric_name=target_name,
                    mean=default_value,
                    median=default_value,
                    min=default_value,
                    max=default_value,
                    std=0.0,
                    last=default_value,
                    n=1,
                    n_missing=0,
                    n_non_zero=1 if default_value != 0 else 0,
                    q10=default_value,
                    q25=default_value,
                    q75=default_value,
                    q90=default_value,
                    q95=default_value,
                    q99=default_value,
                    is_constant=True,
                    all_missing=False,
                    pct_missing=0.0,
                    iqr=0.0,
                    idr=0.0,
                    unit=None,
                    benchmark_ids=[],
                    updated_at=now,
                    test_run_start=now,
                    isArtificial=True,
                )
                self.catalog.ds.metricStatistics.save_object(doc)

            # Reload metric statistics to include the newly created ones
            metric_statistics = self.catalog.ds.metricStatistics.load_objects(
                filter_criteria
            )

        if not metric_statistics:
            # Complete backfilling if no statistics at all and validateWithDefaultIfNoData is True
            if getattr(benchmark.panel, "validateWithDefaultIfNoData", False):
                default_value = getattr(
                    benchmark.panel, "validateWithDefaultIfNoDataValue", 0.0
                )
                from datetime import datetime

                from perfana_ds.schemas.metric_statistics import (
                    MetricStatisticsDocument,
                )

                # Use target names from current test run, or fallback to default
                target_names = (
                    current_target_names
                    if current_target_names
                    else [getattr(benchmark, "metricName", "default")]
                )

                self.logger.info(
                    f"Complete backfilling dsMetricStatistics for {test_run.testRunId} using target names: {target_names}"
                )

                now = datetime.utcnow()
                artificial_targets = []

                # Create artificial dsMetricStatistics for each target name
                for target_name in target_names:
                    doc = MetricStatisticsDocument(
                        test_run_id=test_run.testRunId,
                        application_dashboard_id=getattr(
                            benchmark, "applicationDashboardId", ""
                        ),
                        dashboard_uid=benchmark.dashboardUid,
                        panel_id=benchmark.panel.id,
                        panel_title=benchmark.panel.title,
                        dashboard_label=benchmark.dashboardLabel,
                        metric_name=target_name,
                        mean=default_value,
                        median=default_value,
                        min=default_value,
                        max=default_value,
                        std=0.0,
                        last=default_value,
                        n=1,
                        n_missing=0,
                        n_non_zero=1 if default_value != 0 else 0,
                        q10=default_value,
                        q25=default_value,
                        q75=default_value,
                        q90=default_value,
                        q95=default_value,
                        q99=default_value,
                        is_constant=True,
                        all_missing=False,
                        pct_missing=0.0,
                        iqr=0.0,
                        idr=0.0,
                        unit=None,
                        benchmark_ids=[],
                        updated_at=now,
                        test_run_start=now,
                        isArtificial=True,
                    )
                    self.catalog.ds.metricStatistics.save_object(doc)
                    artificial_targets.append(
                        {
                            "target": target_name,
                            "value": default_value,
                            "isArtificial": True,
                        }
                    )

                panel_average = default_value if artificial_targets else None
                return {"panel_average": panel_average, "targets": artificial_targets}

            self.logger.warning(
                f"No dsMetricStatistics found for testRunId={test_run.testRunId}, panelId={benchmark.panel.id}"
            )
            return {"panel_average": None, "targets": []}

        # If statistics exist, use the regular logic
        evaluate_type = getattr(benchmark.panel, "evaluateType", "mean")
        field_name = self._map_aggregation_type_to_field(
            AggregationType.from_original_name(evaluate_type) or AggregationType.MEAN
        )
        targets = []
        values = []
        for stat in metric_statistics:
            metric_name = getattr(stat, "metric_name", None)
            value = getattr(stat, field_name, None)
            if value is not None and metric_name is not None:
                is_artificial = getattr(stat, "isArtificial", False)
                targets.append(
                    {
                        "target": metric_name,
                        "value": float(value),
                        "isArtificial": is_artificial,
                    }
                )
                values.append(float(value))

        panel_average = None
        if benchmark.averageAll and values:
            panel_average = sum(values) / len(values)
        elif values:
            panel_average = values[0]
        return {"panel_average": panel_average, "targets": targets}

    def _create_compare_result_from_stats(
        self,
        test_run: TestRun,
        baseline_test_run: TestRun,
        benchmark: Benchmark,
        label_snippet: str,
    ) -> CompareResults | None:
        # If no benchmark config, do not create a CompareResults
        benchmark_field = getattr(benchmark.panel, "benchmark", None)
        if not benchmark_field or (
            getattr(benchmark_field, "operator", None) is None
            and getattr(benchmark_field, "value", None) is None
            and getattr(benchmark_field, "absoluteFailureThreshold", None) is None
        ):
            self.logger.info(
                f"No benchmark config for panel {benchmark.panel.id}, skipping CompareResults creation."
            )
            return None

        # Get aggregation for current test run first
        current_agg = self._get_aggregation_result(test_run, benchmark)

        # Get aggregation for baseline/previous test run, using current targets for smart backfilling
        baseline_agg = self._get_aggregation_result_with_smart_backfill(
            baseline_test_run, benchmark, current_agg.get("targets", [])
        )

        if not current_agg["targets"] or not baseline_agg["targets"]:
            self.logger.warning(f"No targets to compare for benchmark {benchmark.id}")
            return None
        # Prepare regex for matchPattern if set
        match_pattern = getattr(benchmark.panel, "matchPattern", None)
        regex = None
        if match_pattern:
            try:
                regex = re.compile(match_pattern)
            except re.error:
                self.logger.warning(f"Invalid matchPattern regex: {match_pattern}")
                regex = None
        # Build target comparisons by matching metric_name
        current_artificial_by_name = {
            t["target"]: t.get("isArtificial", False) for t in current_agg["targets"]
        }
        baseline_artificial_by_name = {
            t["target"]: t.get("isArtificial", False) for t in baseline_agg["targets"]
        }
        # Panel-level artificiality: if only target is 'default' and isArtificial True, mark all as artificial
        panel_current_artificial = (
            len(current_agg["targets"]) == 1
            and current_agg["targets"][0]["target"] == "default"
            and current_agg["targets"][0].get("isArtificial", False)
        )
        panel_baseline_artificial = (
            len(baseline_agg["targets"]) == 1
            and baseline_agg["targets"][0]["target"] == "default"
            and baseline_agg["targets"][0].get("isArtificial", False)
        )
        compare_targets = []
        baseline_targets_by_name = {
            t["target"]: t["value"] for t in baseline_agg["targets"]
        }
        for current_target in current_agg["targets"]:
            target_name = current_target["target"]
            current_value = current_target["value"]
            is_current_artificial = (
                panel_current_artificial
                or current_artificial_by_name.get(target_name, False)
            )
            is_baseline_artificial = (
                panel_baseline_artificial
                or baseline_artificial_by_name.get(target_name, False)
            )
            baseline_value = baseline_targets_by_name.get(target_name)

            # Always calculate changes (regardless of matchPattern)
            absolute_change = None
            percentage_change = None
            if baseline_value is not None:
                absolute_change = current_value - baseline_value
                if baseline_value == 0 and current_value == 0:
                    percentage_change = 0
                elif baseline_value == 0 and current_value != 0:
                    # When baseline is 0 and current is not 0, treat as very large % increase/decrease
                    # Use a large but finite number for better serialization and display
                    percentage_change = 999999.0 if current_value > 0 else -999999.0
                else:
                    percentage_change = (absolute_change / baseline_value) * 100

            # Only skip benchmark evaluation if matchPattern doesn't match
            meets_benchmark = None
            if regex and not regex.search(target_name):
                # Target doesn't match pattern - skip evaluation but keep calculations
                meets_benchmark = None
            elif baseline_value is not None:
                # Target matches pattern (or no pattern) - perform evaluation
                meets_benchmark = self._evaluate_benchmark_comparison(
                    current_value, baseline_value, benchmark.panel.benchmark
                )
            else:
                # No baseline value available - can't evaluate
                meets_benchmark = None

            compare_targets.append(
                CompareResultTarget(
                    target=target_name,
                    rawCurrentValue=current_value,
                    rawBaselineValue=baseline_value,
                    rawDelta=absolute_change,
                    rawDeltaPct=percentage_change,
                    currentValue=current_value,
                    baselineValue=baseline_value,
                    delta=absolute_change,
                    deltaPct=percentage_change,
                    meetsRequirement=meets_benchmark,
                    isCurrentArtificial=is_current_artificial,
                    isBaselineArtificial=is_baseline_artificial,
                )
            )
            if meets_benchmark is False:
                root_meets_benchmark = False
        # Compare panel average
        # Calculate panel averages as the mean of all target values
        current_target_values = [
            t["value"] for t in current_agg["targets"] if t.get("value") is not None
        ]
        baseline_target_values = [
            t["value"] for t in baseline_agg["targets"] if t.get("value") is not None
        ]
        current_panel_avg = (
            sum(current_target_values) / len(current_target_values)
            if current_target_values
            else None
        )
        baseline_panel_avg = (
            sum(baseline_target_values) / len(baseline_target_values)
            if baseline_target_values
            else None
        )
        panel_average_delta = None
        panel_average_delta_pct = None
        if current_panel_avg is not None and baseline_panel_avg is not None:
            panel_average_delta = current_panel_avg - baseline_panel_avg
            panel_average_delta_pct = (
                (panel_average_delta / baseline_panel_avg * 100)
                if baseline_panel_avg != 0
                else None
            )
        panel_meets_benchmark = None
        if current_panel_avg is not None and baseline_panel_avg is not None:
            panel_meets_benchmark = self._evaluate_benchmark_comparison(
                current_panel_avg, baseline_panel_avg, benchmark.panel.benchmark
            )

        # Determine root-level meetsRequirement logic
        if benchmark.averageAll:
            root_meets_benchmark = (
                panel_meets_benchmark if panel_meets_benchmark is not None else True
            )
        else:
            # AND of all target-level meetsRequirement (benchmarkBaselineTestRunOK)
            root_meets_benchmark = all(
                t.meetsRequirement is not False for t in compare_targets
            )

        # Determine final status
        status = ResultStatus.COMPLETE
        # Generate message
        message = self._generate_compare_message(
            root_meets_benchmark,
            len(compare_targets),
            baseline_test_run.testRunId,
            label_snippet,
        )
        # Determine label for uniqueness and clarity
        if label_snippet == "previous test run":
            label = f"{CompareResults.LABEL_AUTO_COMPARE_PREVIOUS_PREFIX}: {baseline_test_run.testRunId}"
        else:
            label = f"{CompareResults.LABEL_AUTO_COMPARE_BASELINE_PREFIX}: {baseline_test_run.testRunId}"
        # Map and log panelType
        panel_type_input = getattr(benchmark.panel, "type", None)
        mapped_panel_type = (
            PanelType.from_original_name(panel_type_input) if panel_type_input else None
        )
        # Create CompareResults document
        compare_result = CompareResults(
            application=test_run.application,
            testEnvironment=test_run.testEnvironment,
            testType=test_run.testType,
            grafana=benchmark.grafana,
            testRunId=test_run.testRunId,
            dashboardLabel=benchmark.dashboardLabel,
            dashboardUid=benchmark.dashboardUid,
            baselineTestRunId=baseline_test_run.testRunId,
            panelTitle=self._strip_panel_title_prefix(benchmark.panel.title),
            panelId=benchmark.panel.id,
            panelType=mapped_panel_type or PanelType.GRAPH,
            panelDescription=getattr(benchmark.panel, "description", None),
            panelYAxesFormat=getattr(benchmark.panel, "yAxesFormat", None),
            benchmarkId=benchmark.id,
            status=status,
            message=message,
            evaluateType=AggregationType.from_original_name(
                benchmark.panel.evaluateType
            )
            or AggregationType.MEAN,
            excludeRampUpTime=benchmark.excludeRampUpTime,
            rampUp=getattr(test_run, "rampUp", 0),
            averageAll=(
                getattr(benchmark.panel, "averageAll", None)
                if getattr(benchmark.panel, "averageAll", None) is not None
                else (benchmark.averageAll or False)
            ),
            matchPattern=match_pattern,
            benchmark=(
                self._convert_benchmark_config(benchmark.panel.benchmark)
                if benchmark.panel.benchmark
                else None
            ),
            meetsRequirement=root_meets_benchmark,
            targets=compare_targets,
            perfanaInfo=f"Created by Perfana Check Pipeline at {datetime.now().isoformat()}",
            label=label,
            currentPanelAverage=current_panel_avg,
            baselinePanelAverage=baseline_panel_avg,
            panelAverageDelta=panel_average_delta,
            panelAverageDeltaPct=panel_average_delta_pct,
        )
        return compare_result

    def _map_aggregation_type_to_field(self, aggregation_type: AggregationType) -> str:
        """Map AggregationType enum to dsMetricStatistics field name."""
        mapping = {
            AggregationType.MEAN: "mean",
            AggregationType.MIN: "min",
            AggregationType.MAX: "max",
            AggregationType.MEDIAN: "median",
            AggregationType.Q10: "q10",
            AggregationType.Q25: "q25",
            AggregationType.Q75: "q75",
            AggregationType.Q90: "q90",
            AggregationType.Q95: "q95",
            AggregationType.Q99: "q99",
            AggregationType.LAST: "last",
            AggregationType.STD: "std",
        }
        return mapping.get(aggregation_type, "mean")

    def _evaluate_benchmark_comparison(
        self, current_value: float, baseline_value: float, benchmark_config: Any
    ) -> bool:
        """Evaluate if current value meets benchmark criteria compared to baseline."""
        absolute_change = current_value - baseline_value

        # Calculate percentage change, handling division by zero
        if baseline_value == 0 and current_value == 0:
            percentage_change = 0
        elif baseline_value == 0 and current_value != 0:
            # When baseline is 0 and current is not 0, treat as very large % increase/decrease
            # Use a large but finite number for better serialization and display
            percentage_change = 999999.0 if current_value > 0 else -999999.0
        else:
            percentage_change = (absolute_change / baseline_value) * 100

        # Handle both Pydantic objects and dictionaries
        if hasattr(benchmark_config, "operator") and hasattr(benchmark_config, "value"):
            operator = benchmark_config.operator
            threshold = benchmark_config.value
            absolute_threshold = getattr(
                benchmark_config,
                "absolute_failure_threshold",
                getattr(benchmark_config, "absoluteFailureThreshold", 0.0),
            )
        elif isinstance(benchmark_config, dict):
            operator = benchmark_config.get("operator", "")
            threshold = benchmark_config.get("value", 0.0)
            absolute_threshold = benchmark_config.get("absoluteFailureThreshold", 0.0)
        else:
            self.logger.warning(
                f"Invalid benchmark config type: {type(benchmark_config)}"
            )
            return True

        if not operator:
            return True

        # Apply benchmark operator with correct absolute failure threshold logic
        operator_str = str(operator).lower()

        # Percentage difference operators with absolute failure threshold
        if operator_str in ["pst-pct", "positive (%)", "percentage_slower_than"]:
            # For pst-pct: Pass if (absolute_change <= absolute_threshold) OR (percentage_change <= threshold)
            if absolute_threshold > 0:
                # Pass if absolute change is within absolute threshold (even if percentage exceeds)
                if abs(percentage_change) >= 999999.0:
                    # For very large percentage, only check absolute threshold
                    return abs(absolute_change) <= absolute_threshold
                else:
                    # Pass if either absolute change is small OR percentage is acceptable
                    return (abs(absolute_change) <= absolute_threshold) or (
                        percentage_change <= threshold
                    )
            else:
                # No absolute threshold, only check percentage
                if abs(percentage_change) >= 999999.0:
                    return False  # Large percentage always fails percentage-based thresholds
                return percentage_change <= threshold

        elif operator_str in ["ngt-pct", "negative (%)", "percentage_faster_than"]:
            # For ngt-pct: Pass if (absolute_change <= absolute_threshold) OR (-percentage_change <= threshold)
            if absolute_threshold > 0:
                # Pass if absolute change is within absolute threshold (even if percentage exceeds)
                if abs(percentage_change) >= 999999.0:
                    # For very large percentage, only check absolute threshold
                    return abs(absolute_change) <= absolute_threshold
                else:
                    # Pass if either absolute change is small OR percentage is acceptable
                    return (abs(absolute_change) <= absolute_threshold) or (
                        -percentage_change <= threshold
                    )
            else:
                # No absolute threshold, only check percentage
                if abs(percentage_change) >= 999999.0:
                    return False  # Large percentage always fails percentage-based thresholds
                return -percentage_change <= threshold

        # Absolute difference operators (no percentage involved)
        elif operator_str in ["pst", "positive"]:
            # Allow positive absolute increase up to threshold
            return absolute_change <= threshold
        elif operator_str in ["ngt", "negative"]:
            # Allow negative absolute decrease up to threshold
            return -absolute_change <= threshold
        else:
            self.logger.warning(f"Unknown benchmark operator: {operator}")
            return True

    def _convert_benchmark_config(self, benchmark_config) -> Any | None:
        """Convert benchmark configuration to a CompareBenchmark instance if possible."""
        if not benchmark_config:
            return None

        # Import here to avoid circular dependencies
        from perfana_ds.schemas.perfana.benchmark import CompareBenchmark

        # If it's already a CompareBenchmark instance, return as-is
        if isinstance(benchmark_config, CompareBenchmark):
            return benchmark_config

        # Handle Pydantic model (BenchmarkField) coming from benchmarks collection
        if hasattr(benchmark_config, "operator") and hasattr(benchmark_config, "value"):
            operator_value = benchmark_config.operator
            value_value = benchmark_config.value
            abs_threshold = getattr(benchmark_config, "absoluteFailureThreshold", 0.0)

            # If no operator specified, we cannot convert – return None
            if not operator_value:
                return None

            # Map operator string to BenchmarkOperator enum
            try:
                if isinstance(operator_value, BenchmarkOperator):
                    operator_enum = operator_value
                else:
                    operator_enum = BenchmarkOperator(operator_value.lower())
            except ValueError:
                # Unknown operator – skip conversion
                return None

            # Ensure value is not None
            if value_value is None:
                return None

            return CompareBenchmark(
                operator=operator_enum,
                value=float(value_value),
                absolute_failure_threshold=float(abs_threshold or 0.0),
            )

        # If it's a plain dictionary
        if isinstance(benchmark_config, dict):
            operator = benchmark_config.get("operator")
            value = benchmark_config.get("value")
            abs_threshold = benchmark_config.get("absoluteFailureThreshold", 0.0)

            if not operator or value is None:
                return None

            try:
                operator_enum = BenchmarkOperator(operator.lower())
            except ValueError:
                return None

            return CompareBenchmark(
                operator=operator_enum,
                value=float(value),
                absolute_failure_threshold=float(abs_threshold or 0.0),
            )

        # Fallback – unsupported type
        return None

    def _generate_compare_message(
        self,
        meets_benchmark: bool,
        target_count: int,
        baseline_test_run_id: str,
        label_snippet: str,
    ) -> str:
        """Generate a message for the compare result."""
        if target_count == 0:
            return (
                f"No targets to compare against {label_snippet} {baseline_test_run_id}"
            )

        if meets_benchmark:
            return f"✅ All {target_count} targets meet benchmark criteria compared to {label_snippet} {baseline_test_run_id}"
        else:
            return f"❌ Some targets failed benchmark comparison against {label_snippet} {baseline_test_run_id}"

    def batch_create_compare_results(
        self, check_results: list[CheckResults], force_recreate: bool = False
    ) -> list[CompareResults]:
        """Create compare results for multiple check results in batch."""
        created_results = []

        for check_result in check_results:
            try:
                # Skip if compare result already exists (unless force recreate)
                if not force_recreate:
                    existing = self.catalog.compareResults.load_object(
                        {
                            "testRunId": check_result.testRunId,
                            "benchmarkId": check_result.benchmarkId,
                        }
                    )
                    if existing:
                        self.logger.debug(
                            f"Compare result already exists for {check_result.id}"
                        )
                        continue

                # Get test run and benchmark
                test_run = self.catalog.testRuns.load_object(
                    {"testRunId": check_result.testRunId}
                )
                benchmark = self.catalog.benchmarks.load_object(
                    {"_id": check_result.benchmarkId}
                )

                if not test_run or not benchmark:
                    self.logger.warning(
                        f"Missing test run or benchmark for {check_result.id}"
                    )
                    continue

                # Create compare results (both previous and baseline if available)
                compare_result_prev = self.create_compare_result_previous(
                    test_run, benchmark
                )
                if compare_result_prev:
                    self.catalog.compareResults.save_object(compare_result_prev)
                    created_results.append(compare_result_prev)

                compare_result_baseline = self.create_compare_result_baseline(
                    test_run, benchmark
                )
                if compare_result_baseline:
                    self.catalog.compareResults.save_object(compare_result_baseline)
                    created_results.append(compare_result_baseline)

            except Exception as e:
                self.logger.error(
                    f"Failed to process check result {check_result.id}: {e}"
                )

        self.logger.info(
            f"Created {len(created_results)} compare results from {len(check_results)} check results"
        )
        return created_results

    def _strip_panel_title_prefix(self, title: str) -> str:
        if not title:
            return title
        if "-" in title:
            return title.split("-", 1)[1].strip()
        return title
