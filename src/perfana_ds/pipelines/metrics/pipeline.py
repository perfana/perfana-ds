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

from time import time

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.pipelines.metrics.nodes import (
    get_benchmark_panel_metrics,
    get_non_benchmark_panel_metrics,
    logger,
)
from perfana_ds.pipelines.metrics.reevaluate import (
    find_benchmarks_mapping,
    find_missing_benchmark_metrics,
    get_panels_for_missing_metrics,
    update_benchmark_ids_for_panels_and_metrics,
)
from perfana_ds.pipelines.panels.pipeline import run_panels_pipeline
from perfana_ds.pipelines.statistics.pipeline import run_metric_statistics_pipeline
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument


def run_metrics_pipeline(
    test_run_id: str,
    benchmarks_only: bool = False,
    panel_documents: list[PanelDocument] | None = None,
) -> list[PanelMetricsDocument]:
    logger.info(f"Creating metrics for test run {test_run_id}")
    start_time = time()
    catalog = get_catalog()
    test_run = catalog.testRuns.load_object({"testRunId": test_run_id})
    if test_run is None:
        raise FileNotFoundError(
            f"Test run {test_run_id} not found in {catalog.testRuns.collection_name}"
        )

    if panel_documents is None:
        panel_documents = catalog.ds.panels.load_objects({"testRunId": test_run_id})

    metrics = []
    metrics_benchmarks = get_benchmark_panel_metrics(
        test_run=test_run,
        panel_documents=panel_documents,
        grafanas_collection=catalog.grafanas.collection,
    )
    if len(metrics_benchmarks) > 0:
        catalog.ds.metrics.save_objects(metrics_benchmarks)
    metrics.extend(metrics_benchmarks)

    if benchmarks_only is False:
        metrics_non_benchmarks = get_non_benchmark_panel_metrics(
            test_run=test_run,
            panel_documents=panel_documents,
            grafanas_collection=catalog.grafanas.collection,
        )
        if len(metrics_non_benchmarks) > 0:
            catalog.ds.metrics.save_objects(metrics_non_benchmarks)
        metrics.extend(metrics_non_benchmarks)

    logger.info(
        f"Finished getting {len(metrics)} metrics in {(time() - start_time):.2f} seconds"
    )
    return metrics


def run_reevaluate_pipeline(test_run_id: str) -> list[PanelMetricsDocument]:
    """Pipeline to re-evaluate perfana-check by updating metrics with benchmarks only.

    If panels with benchmarks are not yet found in dsMetrics or dsPanels, they are created. All
    benchmark metrics that already have docs in dsMetrics will be updated with their current benchmarkIds,
    which will trigger perfana-check even if no data is refreshed.
    """
    start_time = time()
    catalog = get_catalog()
    logger.info(f"Re-evaluating metrics with benchmarks for {test_run_id}")
    test_run = catalog.testRuns.load_object({"testRunId": test_run_id})

    benchmarks_mapping = find_benchmarks_mapping(catalog, test_run)
    missing_benchmark_metrics = find_missing_benchmark_metrics(
        catalog, test_run_id, benchmarks_mapping
    )
    logger.info(
        f"Found {len(missing_benchmark_metrics)} missing panels with benchmarks for {test_run_id}"
    )
    logger.debug(
        f"Re-evaluate benchmarks: {missing_benchmark_metrics} for {test_run_id}"
    )
    if len(missing_benchmark_metrics) > 0:
        logger.info(f"Update all Panels to re-evaluate for {test_run_id}")
        run_panels_pipeline(test_run_id=test_run_id)

        missing_panels = get_panels_for_missing_metrics(
            catalog, test_run_id, missing_benchmark_metrics
        )

        metrics = run_metrics_pipeline(
            test_run_id=test_run_id, panel_documents=missing_panels
        )
    else:
        metrics = []

    update_benchmark_ids_for_panels_and_metrics(
        catalog, test_run_id, benchmarks_mapping
    )

    run_metric_statistics_pipeline(test_run_ids=[test_run_id])

    logger.info(
        f"Finished re-evaluating metrics in {(time() - start_time):.2f} seconds"
    )
    return metrics
