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

"""Service for aggregating dsMetric data according to benchmark specifications."""

import logging
from datetime import datetime
from typing import Any

from perfana_ds.catalog.catalog import Catalog
from perfana_ds.schemas.metric_statistics import MetricStatisticsDocument
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.enums import AggregationType
from perfana_ds.schemas.perfana.test_runs import TestRun

from .base import BaseCheckService, DataAggregationError


class DataAggregator(BaseCheckService):
    """Minimal service to fetch pre-aggregated metrics from dsMetricStatistics."""

    def __init__(self, catalog: Catalog):
        super().__init__()
        self.catalog = catalog

    def aggregate_metrics_for_benchmark(
        self, test_run: TestRun, benchmark: Benchmark
    ) -> dict[str, Any]:
        """Fetch aggregated metrics for a specific benchmark from dsMetricStatistics."""
        try:
            # self.logger.info(
            #     f"Aggregating metrics for benchmark {benchmark.id} "
            #     f"on test run {test_run.testRunId}"
            # )
            filter_criteria = {
                "testRunId": test_run.testRunId,
                "dashboardUid": benchmark.dashboardUid,
                "dashboardLabel": benchmark.dashboardLabel,
                "panelId": benchmark.panel.id,
            }

            metric_statistics = self.catalog.ds.metricStatistics.load_objects(
                filter_criteria
            )
            # self.logger.info(f"Loaded {len(metric_statistics) if metric_statistics else 0} dsMetricStatistics docs for filter: {filter_criteria}")
            if not metric_statistics:
                logger = logging.getLogger(
                    "perfana_ds.pipelines.checks.data_aggregator"
                )
                logger.debug(
                    f"No metric_statistics found for filter: {filter_criteria}"
                )
                logger.debug(
                    f"benchmark.panel.validateWithDefaultIfNoData: {getattr(benchmark.panel, 'validateWithDefaultIfNoData', None)}; benchmark.panel.validateWithDefaultIfNoDataValue: {getattr(benchmark.panel, 'validateWithDefaultIfNoDataValue', None)}"
                )
                if getattr(benchmark.panel, "validateWithDefaultIfNoData", False):
                    logger.info(
                        f"Backfilling artificial dsMetricStatistics for panel {benchmark.panel.id} in test run {test_run.testRunId}"
                    )
                    default_value = getattr(
                        benchmark.panel, "validateWithDefaultIfNoDataValue", 0.0
                    )
                    # Create and save a default dsMetricStatistics document
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
                    # Return aggregation result with isArtificial: True
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
                    f"No metrics data found for panel {benchmark.panel.id} "
                    f"in test run {test_run.testRunId}"
                )
                return {"panel_average": None, "targets": []}

            evaluate_type = getattr(benchmark.panel, "evaluateType", "mean")
            field_name = self._map_aggregation_type_to_field(
                AggregationType.from_original_name(evaluate_type)
                or AggregationType.MEAN
            )
            targets = []
            values = []
            # If only one metric_statistic and it is artificial, treat all targets as artificial
            if len(metric_statistics) == 1 and getattr(
                metric_statistics[0], "isArtificial", False
            ):
                targets = [
                    {
                        "target": "default",
                        "value": metric_statistics[0].mean,
                        "isArtificial": True,
                    }
                ]
                panel_average = metric_statistics[0].mean
                return {"panel_average": panel_average, "targets": targets}
            for stat in metric_statistics:
                metric_name = getattr(stat, "metric_name", None)
                value = getattr(stat, field_name, None)
                # self.logger.info(f"  metric_name: {metric_name}, {field_name}: {value}")
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
            if not targets:
                return {"panel_average": None, "targets": []}
            panel_average = None
            if benchmark.averageAll:
                panel_average = sum(values) / len(values) if values else None
            elif values:
                panel_average = values[0]
            return {"panel_average": panel_average, "targets": targets}
        except Exception as e:
            raise DataAggregationError(
                f"Failed to aggregate metrics for benchmark {benchmark.id}: {str(e)}"
            )

    def _map_aggregation_type_to_field(self, aggregation_type: AggregationType) -> str:
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

    def process(self, test_run: TestRun, benchmark: Benchmark) -> dict[str, Any]:
        return self.aggregate_metrics_for_benchmark(test_run, benchmark)
