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

from typing import Annotated

from celery.utils.log import get_task_logger
from fastapi import APIRouter, Query

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.datasets.mongo_data import MongoData

router = APIRouter()

logger = get_task_logger(__name__)


def _create_index_if_required(dataset: MongoData, flag: bool):
    if flag is True:
        dataset.create_index()


@router.post("/createIndexes")
def create_indexes(
    panels: Annotated[bool, Query()] = True,
    metrics: Annotated[bool, Query()] = True,
    metricStatistics: Annotated[bool, Query()] = True,
    controlGroups: Annotated[bool, Query()] = True,
    controlGroupStatistics: Annotated[bool, Query()] = True,
    trackedDifferences: Annotated[bool, Query()] = True,
    adaptInput: Annotated[bool, Query()] = True,
    adaptResults: Annotated[bool, Query()] = True,
    adaptConclusion: Annotated[bool, Query()] = True,
    adaptTrackedResults: Annotated[bool, Query()] = True,
):
    catalog = get_catalog()
    _create_index_if_required(catalog.ds.panels, flag=panels)
    _create_index_if_required(catalog.ds.metrics, flag=metrics)
    _create_index_if_required(catalog.ds.metricStatistics, flag=metricStatistics)
    _create_index_if_required(catalog.ds.controlGroup, flag=controlGroups)
    _create_index_if_required(
        catalog.ds.controlGroupStatistics, flag=controlGroupStatistics
    )
    _create_index_if_required(catalog.ds.trackedDifferences, flag=trackedDifferences)
    _create_index_if_required(catalog.ds.adaptInput, flag=adaptInput)
    _create_index_if_required(catalog.ds.adaptResults, flag=adaptResults)
    _create_index_if_required(catalog.ds.adaptConclusion, flag=adaptConclusion)
    _create_index_if_required(catalog.ds.adaptTrackedResults, flag=adaptTrackedResults)
    return True


@router.post("/createSchemas")
def create_schemas(
    panels: Annotated[bool, Query()] = True,
    metrics: Annotated[bool, Query()] = True,
    metricStatistics: Annotated[bool, Query()] = True,
    controlGroupStatistics: Annotated[bool, Query()] = True,
    trackedDifferences: Annotated[bool, Query()] = True,
    adaptInput: Annotated[bool, Query()] = True,
    adaptResults: Annotated[bool, Query()] = True,
    adaptTrackedResults: Annotated[bool, Query()] = True,
    adaptConclusion: Annotated[bool, Query()] = True,
):
    """Create database collection schemas in MongoDB for data validation"""
    catalog = get_catalog()
    _create_schema_for_dataset(catalog.ds.panels, flag=panels)
    _create_schema_for_dataset(catalog.ds.metrics, flag=metrics)
    _create_schema_for_dataset(catalog.ds.metricStatistics, flag=metricStatistics)
    _create_schema_for_dataset(
        catalog.ds.controlGroupStatistics, flag=controlGroupStatistics
    )
    _create_schema_for_dataset(catalog.ds.adaptInput, flag=adaptInput)
    _create_schema_for_dataset(catalog.ds.adaptResults, flag=adaptResults)
    _create_schema_for_dataset(catalog.ds.trackedDifferences, flag=trackedDifferences)
    _create_schema_for_dataset(catalog.ds.adaptTrackedResults, flag=adaptConclusion)
    _create_schema_for_dataset(catalog.ds.adaptConclusion, flag=adaptTrackedResults)
    return True


def _create_schema_for_dataset(dataset: MongoData, flag: bool = True):
    if flag is True:
        logger.info(
            f"Creating schema for {dataset.database_name}.{dataset.collection_name} using {dataset.data_model.__name__}"
        )
        create_and_check_schema(
            dataset.database,
            dataset.collection_name,
            dataset.upsert_fields,
            dataset.data_model.mongodb_schema(),
        )
        logger.info(
            f"Schema succesfully created for {dataset.database_name}.{dataset.collection_name}"
        )
    else:
        logger.info(
            f"Skip creating schema for {dataset.database_name}.{dataset.collection_name}"
        )
    return True


def create_and_check_schema(db, collection_name, upsert_fields, schema: dict):
    db.command({"collMod": collection_name, "validator": schema})
    cursor = db[collection_name].find({"$nor": [schema]}).limit(100)
    bad_docs = list(cursor)
    if len(bad_docs) > 0:
        bad_doc = bad_docs[0]
        for field in upsert_fields:
            bad_doc[field] = "test"

        replace_filter = {field: bad_doc[field] for field in upsert_fields}
        try:
            db[collection_name].find_one_and_replace(
                filter=replace_filter, replacement=bad_doc, upsert=True
            )
        except Exception as e:
            logger.error(e)

        db.command({"collMod": collection_name, "validator": {}})
        raise ValueError(
            f"Schema error in {db.name}.{collection_name}. Found at least {len(bad_docs)} that do not match the new schema. Removed schema."
        )
    return True
