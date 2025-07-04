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

from collections.abc import MutableMapping
from typing import Any

from celery.utils.log import get_task_logger
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pydantic import BaseModel
from pymongo import IndexModel, ReplaceOne
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DocumentTooLarge

from perfana_ds.datasets.mongo import BaseMongoDataset
from perfana_ds.project_settings import get_settings

logger = get_task_logger(__name__)
settings = get_settings()


def create_indexes_if_not_exists(
    collection: Collection,
    index_fields: dict[str, int | str],
    unique_index: bool = True,
) -> MutableMapping[str, Any]:
    """Create indexes on the index_fields for a mongodb collection."""
    current_indices = set(collection.index_information().keys())
    target_indices = set(index_fields.keys())

    indices_to_drop = (current_indices - target_indices) - {"_id"} - {"_id_"}
    dropped_indices = []
    logger.info(f"Dropping indices in {collection.name}: {indices_to_drop}.")
    for index_key, index in collection.index_information().items():
        if index_key in ["_id", "_id_"]:
            continue
        else:
            dropped_indices.append(index_key)
            collection.drop_index(index_key)
    logger.info(f"Dropped indices in {collection.name}: {dropped_indices}.")

    # create index per field
    index_models = []
    logger.info(f"Creating indices in {collection.name}: {index_fields}.")
    for field, direction in index_fields.items():
        index_model = IndexModel([(field, direction)], name=field)
        index_models.append(index_model)
    collection.create_indexes(index_models)

    # create unique compound index
    if unique_index:
        logger.info(f"Creating unique index in {collection.name} for {index_fields}.")
        collection.create_index(index_fields, unique=True)

    logger.info(
        f"Resulting indices of {collection.name}: {set(collection.index_information())}"
    )
    return collection.index_information()


class MongoData(BaseMongoDataset):
    database_name: str
    collection_name: str
    data_model: type[BaseModel] | None = None
    engine_kwargs: dict[str, Any] | None = None
    read_only: bool = True
    upsert_fields: list[str] | None = None
    index_fields: dict[str, int | str] | None = None
    unique_index: bool = True

    @property
    def database(self) -> Database:
        return self.client[self.database_name]

    @property
    def collection(self) -> Collection:
        return self.database[self.collection_name]

    @property
    def async_database(self) -> AsyncIOMotorDatabase:
        return self.async_client[self.database_name]

    @property
    def async_collection(self) -> AsyncIOMotorCollection:
        return self.async_database[self.collection_name]

    def create_index(self) -> MutableMapping[str, Any] | None:
        if self.index_fields is not None:
            return create_indexes_if_not_exists(
                collection=self.collection,
                index_fields=self.index_fields,
                unique_index=self.unique_index,
            )
        else:
            return None

    def save(self, data: list[dict[str, Any]]):  # type: ignore [override]
        raise NotImplementedError("Cannot write to Collection dataset.")

    def save_object(self, data: BaseModel | dict[str, Any]):  # type: ignore [override]
        if self.read_only:
            raise PermissionError("Cannot write to read-only dataset.")

        if self.upsert_fields is None:
            raise ValueError("Cannot save dataset without upsert fields")

        validated_object = self.data_model.model_validate(data)
        validated_doc = validated_object.model_dump(by_alias=True)
        replace_filter = {field: validated_doc[field] for field in self.upsert_fields}
        result = self.collection.find_one_and_replace(
            filter=replace_filter, replacement=validated_doc, upsert=True
        )
        return result

    def load_object(self, filter, **kwargs):  # type: ignore [override]
        doc = self.collection.find_one(filter, **kwargs)
        result = self.data_model.model_validate(doc) if doc is not None else None
        return result

    async def load_object_async(self, filter, **kwargs):  # type: ignore [override]
        doc = await self.async_collection.find_one(filter, **kwargs)
        result = self.data_model.model_validate(doc) if doc is not None else None
        return result

    def load_objects(self, filter, **kwargs):  # type: ignore [override]
        cursor = self.collection.find(filter)
        if "sort" in kwargs:
            cursor.sort(kwargs["sort"])
        docs = list(cursor)
        if not docs:
            return None
        if self.data_model is not None:
            result = (
                [self.data_model.model_validate(x) for x in docs]
                if docs is not None
                else None
            )
        else:
            result = docs
        return result

    async def load_objects_async(self, filter, **kwargs):  # type: ignore [override]
        async_cursor = self.async_collection.find(filter, **kwargs)
        docs = await async_cursor.to_list(length=None)
        if self.data_model is not None:
            result = (
                [self.data_model.model_validate(x) for x in docs]
                if docs is not None
                else None
            )
        else:
            result = docs
        return result

    async def save_object_async(self, data: BaseModel | dict[str, Any]):  # type: ignore [override]
        if self.read_only:
            raise PermissionError("Cannot write to read-only dataset.")

        if self.upsert_fields is None:
            raise ValueError("Cannot save dataset without upsert fields")

        validated_object = self.data_model.model_validate(data)
        validated_doc = validated_object.model_dump(by_alias=True)
        replace_filter = {field: validated_doc[field] for field in self.upsert_fields}
        result = await self.async_collection.find_one_and_replace(
            filter=replace_filter, replacement=validated_doc, upsert=True
        )
        return result

    def save_objects(self, data: list[BaseModel] | list[dict[str, Any]], batch_size: int | None = None):  # type: ignore [override]
        if batch_size is None:
            batch_size = settings.MONGO_BATCH_SIZE

        if self.read_only:
            raise PermissionError("Cannot write to read-only dataset.")

        if self.upsert_fields is None:
            raise ValueError("Cannot save dataset without upsert fields")

        validated_objects = [self.data_model.model_validate(x) for x in data]
        validated_docs = [x.model_dump(by_alias=True) for x in validated_objects]

        results = []
        for i in range(0, len(validated_docs), batch_size):
            batch = validated_docs[i : i + batch_size]
            update_queries = [
                ReplaceOne(
                    {key: doc[key] for key in self.upsert_fields},
                    doc,
                    upsert=True,
                )
                for doc in batch
            ]
            logger.info(
                f"Saving batch {i//batch_size + 1} of {len(validated_docs)//batch_size + 1} to {self.collection.name}"
            )
            try:
                result = self.collection.bulk_write(update_queries)
                results.append(result)
            except DocumentTooLarge:
                if batch_size > 1:
                    # Recursively try with smaller batch size
                    new_batch_size = max(1, batch_size // 2)
                    logger.info(
                        f"Reducing batch size to {new_batch_size} due to DocumentTooLarge error"
                    )
                    sub_results = self.save_objects(
                        validated_objects[i:], batch_size=new_batch_size
                    )
                    results.extend(sub_results)
                    break
                else:
                    # Skip this document if batch size is already 1
                    logger.warning(
                        f"Skipping document in {self.collection.name} due to DocumentTooLarge error"
                    )
                    continue

        return results

    async def save_objects_async(self, data: list[BaseModel] | list[dict[str, Any]]):  # type: ignore [override]
        if self.read_only:
            raise PermissionError("Cannot write to read-only dataset.")

        if self.upsert_fields is None:
            raise ValueError("Cannot save dataset without upsert fields")

        validated_objects = [self.data_model.model_validate(x) for x in data]
        validated_docs = [x.model_dump(by_alias=True) for x in validated_objects]
        update_queries = [
            ReplaceOne(
                {key: validated_doc[key] for key in self.upsert_fields},
                validated_doc,
                upsert=True,
            )
            for validated_doc in validated_docs
        ]
        result = await self.async_client.bulk_write(update_queries)
        return result
