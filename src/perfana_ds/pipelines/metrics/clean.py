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

from collections import defaultdict
from typing import Any

import pandas as pd

from perfana_ds.schemas.perfana.test_runs import TestRun


def add_metric_metadata_to_dataframe(
    df: pd.DataFrame, test_run: TestRun
) -> pd.DataFrame:
    if df.shape[0] > 0:
        timestep = (df["time"] - test_run.start).dt.total_seconds()
        ramp_up = timestep < test_run.rampUp
        df = df.assign(timestep=timestep, ramp_up=ramp_up)
    else:
        df = df.assign(timestep=[], ramp_up=[])
    return df


def find_duplicates(x: list[Any]) -> list[list[int]]:
    duplicates = defaultdict(list)
    for i, ele in enumerate(x):
        duplicates[ele].append(i)
    return [v for k, v in duplicates.items() if len(v) > 1]


def combine_duplicate_documents_data(objects: list[Any], fields) -> list[Any]:
    object_fields = [(getattr(x, field) for field in fields) for x in objects]
    duplicates = find_duplicates(object_fields)
    indices_to_drop = []
    for duplicate_indices in duplicates:
        for duplicate_index in duplicate_indices[1:]:
            indices_to_drop.append(duplicate_index)
            data_to_extend = objects[duplicate_index].data
            if data_to_extend is not None:
                objects[duplicate_indices[0]].data.extend(data_to_extend)
    result = [x for i, x in enumerate(objects) if i not in indices_to_drop]
    return result
