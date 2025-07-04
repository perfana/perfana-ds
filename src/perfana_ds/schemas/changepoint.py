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

from bson import ObjectId
from pydantic import ConfigDict

from perfana_ds.schemas.base_document import BaseDocument


class Changepoint(BaseDocument):
    """Indicator of a changepoint for a test run or specific metric."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: ObjectId | None = None
    application: str
    test_type: str
    test_environment: str
    test_run_id: str
    application_dashboard_id: str | None = None
    panel_title: str | None = None
    dashboard_label: str | None = None
    dashboard_uid: str | None = None
    panel_id: int | None = None
    metric_name: str | None = None

    @property
    def mongo_filter(self):
        """Filter on dsMetrics to select metric"""
        return {
            "applicationDashboardId": self.application_dashboard_id,
            "panelId": self.panel_id,
        }
