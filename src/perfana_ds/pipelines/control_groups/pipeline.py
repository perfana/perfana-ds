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

from perfana_ds.pipelines.control_groups.create import (
    aggregate_control_groups,
)
from perfana_ds.pipelines.statistics.aggregation import (
    aggregate_control_group_statistics,
)
from perfana_ds.schemas.control_groups import ControlGroup

logger = get_task_logger(__name__)


def run_control_groups_pipeline(test_run_ids: list[str]) -> list[ControlGroup]:
    logger.info(f"Creating control groups for {len(test_run_ids)} test runs")
    start_time = time()

    sub_start_time = time()
    control_groups = aggregate_control_groups(test_run_ids=test_run_ids)
    logger.info(
        f"Created {len(control_groups)} control groups in {(time() - sub_start_time):.2f} seconds"
    )

    sub_start_time = time()
    logger.info(
        f"Calculating control group statistics for {len(control_groups)} control groups"
    )
    _ = aggregate_control_group_statistics(control_groups=control_groups)
    logger.info(
        f"Finished  control group statistics in {(time() - sub_start_time):.2f} seconds"
    )
    logger.info(
        f"Finished creating control groups in {(time() - start_time):.2f} seconds"
    )
    return control_groups
