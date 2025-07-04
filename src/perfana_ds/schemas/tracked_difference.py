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

import typing
from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from perfana_ds.schemas.adapt_result import ConclusionResult
from perfana_ds.schemas.base_document import BaseMetricDocument

DIFFERENCE_LABELS_TYPE = Literal["increase", "decrease", "regression", "improvement"]
DIFFERENCE_LABELS = list(typing.get_args(DIFFERENCE_LABELS_TYPE))


class TrackedDifferenceDocument(BaseMetricDocument):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, arbitrary_types_allowed=True
    )
    test_run_start: datetime
    control_group_id: str
    panel_title: str
    dashboard_label: str
    dashboard_uid: str
    label: str
    status: Literal["ACCEPTED", "TBD", "DENIED"]
    checked_at: datetime
    latest: bool
    adapt_result_id: ObjectId
    conclusion: ConclusionResult
