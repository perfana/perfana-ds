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

from __future__ import annotations

from pydantic import BaseModel

from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.project_settings import Settings
from perfana_ds.schemas.adapt_conclusion import AdaptConclusionDocument
from perfana_ds.schemas.adapt_result import (
    AdaptResultDocument,
    AdaptTrackedResultDocument,
)
from perfana_ds.schemas.changepoint import Changepoint
from perfana_ds.schemas.compare_config import CompareConfigDocument
from perfana_ds.schemas.control_group_statistics import ControlGroupStatisticsDocument
from perfana_ds.schemas.control_groups import ControlGroup
from perfana_ds.schemas.metric_comparison import (
    ControlGroupComparisonDocument,
)
from perfana_ds.schemas.metric_statistics import MetricStatisticsDocument
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
from perfana_ds.schemas.tracked_difference import TrackedDifferenceDocument


class dsCatalog(BaseModel):
    panels: MongoData
    metrics: MongoData
    metricStatistics: MongoData
    trackedDifferences: MongoData
    changePoints: MongoData
    controlGroup: MongoData
    controlGroupStatistics: MongoData
    compareConfig: MongoData
    adaptInput: MongoData
    adaptResults: MongoData
    adaptTrackedResults: MongoData
    adaptConclusion: MongoData

    @classmethod
    def from_settings(cls, settings: Settings = None) -> dsCatalog:
        return dsCatalog(
            controlGroup=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsControlGroups",
                read_only=False,
                data_model=ControlGroup,
                upsert_fields=["controlGroupId"],
                index_fields={"controlGroupId": 1},
            ),
            panels=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsPanels",
                read_only=False,
                data_model=PanelDocument,
                upsert_fields=["testRunId", "applicationDashboardId", "panelId"],
                index_fields={
                    "testRunId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                },
            ),
            metrics=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsMetrics",
                read_only=False,
                data_model=PanelMetricsDocument,
                upsert_fields=[
                    "testRunId",
                    "applicationDashboardId",
                    "panelId",
                ],
                index_fields={
                    "testRunId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                },
            ),
            metricStatistics=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsMetricStatistics",
                read_only=False,
                data_model=MetricStatisticsDocument,
                upsert_fields=[
                    "testRunId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "testRunId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            trackedDifferences=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsTrackedDifferences",
                read_only=False,
                data_model=TrackedDifferenceDocument,
                upsert_fields=[
                    "testRunId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "testRunId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            changePoints=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                data_model=Changepoint,
                collection_name="dsChangepoints",
                read_only=True,
            ),
            controlGroupStatistics=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                data_model=ControlGroupStatisticsDocument,
                collection_name="dsControlGroupStatistics",
                upsert_fields=[
                    "controlGroupId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "controlGroupId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            compareConfig=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsCompareConfig",
                read_only=False,
                data_model=CompareConfigDocument,
                upsert_fields=[
                    "application",
                    "testType",
                    "testEnvironment",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "application": 1,
                    "testType": 1,
                    "testEnvironment": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            adaptInput=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsAdaptInput",
                data_model=ControlGroupComparisonDocument,
                upsert_fields=[
                    "testRunId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "testRunId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            adaptTrackedResults=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsAdaptTrackedResults",
                data_model=AdaptTrackedResultDocument,
                upsert_fields=[
                    "testRunId",
                    "controlGroupId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "testRunId": 1,
                    "controlGroupId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            adaptResults=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsAdaptResults",
                data_model=AdaptResultDocument,
                upsert_fields=[
                    "testRunId",
                    "controlGroupId",
                    "applicationDashboardId",
                    "panelId",
                    "metricName",
                ],
                index_fields={
                    "testRunId": 1,
                    "controlGroupId": 1,
                    "applicationDashboardId": 1,
                    "panelId": 1,
                    "metricName": 1,
                },
            ),
            adaptConclusion=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dsAdaptConclusion",
                read_only=False,
                data_model=AdaptConclusionDocument,
                upsert_fields=[
                    "testRunId",
                ],
                index_fields={
                    "testRunId": 1,
                },
            ),
        )
