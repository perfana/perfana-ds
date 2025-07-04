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

from celery.utils.log import get_task_logger

from perfana_ds.pipelines.statistics.aggregation import (
    aggregate_metric_statistics,
)

logger = get_task_logger(__name__)


def run_metric_statistics_pipeline(test_run_ids: list[str]) -> bool:
    logger.info(f"Aggregating metric statistics for test runs: {test_run_ids}")
    start_time = time()
    if len(test_run_ids) == 0:
        raise ValueError("No test runs provided.")

    aggregate_metric_statistics(test_run_ids=test_run_ids)
    logger.info(
        f"Finished aggregating statistics in {(time() - start_time):.2f} seconds"
    )
    return True
