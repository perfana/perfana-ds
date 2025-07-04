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

from functools import lru_cache

from pydantic import BaseModel

from perfana_ds.catalog.ds import dsCatalog
from perfana_ds.datasets.mongo import BaseMongoDataset
from perfana_ds.datasets.mongo_data import MongoData
from perfana_ds.project_settings import Settings, get_settings
from perfana_ds.schemas.perfana.application_dashboards import ApplicationDashboard
from perfana_ds.schemas.perfana.applications import Application
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.check_results import CheckResults
from perfana_ds.schemas.perfana.compare_results import CompareResults
from perfana_ds.schemas.perfana.grafana_dashboards import GrafanaDashboard
from perfana_ds.schemas.perfana.test_runs import TestRun
from perfana_ds.schemas.dynatrace_dql import DynatraceDqlDocument


class Catalog(BaseModel):
    client: BaseMongoDataset
    testRuns: MongoData
    applications: MongoData
    applicationDashboards: MongoData
    grafanaDashboards: MongoData
    grafanas: MongoData
    dynatrace: MongoData
    dynatrace_dql: MongoData
    benchmarks: MongoData
    checkResults: MongoData
    compareResults: MongoData

    ds: dsCatalog

    @classmethod
    def from_settings(cls, settings: Settings) -> Catalog:
        return Catalog(
            client=BaseMongoDataset(con=settings.MONGO_URL),
            testRuns=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="testRuns",
                read_only=True,
                data_model=TestRun,
            ),
            applications=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="applications",
                read_only=True,
                data_model=Application,
            ),
            applicationDashboards=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="applicationDashboards",
                read_only=True,
                data_model=ApplicationDashboard,
            ),
            grafanaDashboards=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="grafanaDashboards",
                read_only=True,
                data_model=GrafanaDashboard,
            ),
            grafanas=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="grafanas",
                read_only=True,
                data_model=None,
            ),
            dynatrace=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dynatrace",
                read_only=True,
                data_model=None,
            ),
            dynatrace_dql=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="dynatraceDql",
                read_only=False,
                data_model=DynatraceDqlDocument,
                index_fields={
                    "application": 1,
                    "testEnvironment": 1,
                    "dashboardUid": 1,
                },
            ),
            benchmarks=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="benchmarks",
                read_only=True,
                data_model=Benchmark,
            ),
            checkResults=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="checkResults",
                read_only=False,
                data_model=CheckResults,
                upsert_fields=["testRunId", "benchmarkId"],
                index_fields={
                    "testRunId": 1,
                    "benchmarkId": 1,
                    "application": 1,
                    "testType": 1,
                    "testEnvironment": 1,
                },
            ),
            compareResults=MongoData(
                con=settings.MONGO_URL,
                database_name=settings.MONGO_DB,
                collection_name="compareResults",
                read_only=False,
                data_model=CompareResults,
                upsert_fields=["testRunId", "benchmarkId", "label"],
                index_fields={
                    "testRunId": 1,
                    "benchmarkId": 1,
                    "label": 1,
                    "application": 1,
                    "testType": 1,
                    "testEnvironment": 1,
                },
            ),
            ds=dsCatalog.from_settings(settings),
        )


@lru_cache
def get_catalog(settings: Settings = None) -> Catalog:
    if settings is None:
        settings = get_settings()

    return Catalog.from_settings(settings)
