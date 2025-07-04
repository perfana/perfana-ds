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

import logging
from logging import Logger
from typing import Any, ClassVar

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ConfigDict, Field, field_validator
from pydantic.networks import MongoDsn
from pymongo import MongoClient

from perfana_ds.datasets.abstract import BaseDataset


class BaseMongoDataset(BaseDataset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    default_engine_kwargs: ClassVar[dict[str, Any]] = dict(
        connectTimeoutMS=3000, tz_aware=True, connect=False
    )
    clients: ClassVar[dict[str, MongoClient]] = {}
    async_clients: ClassVar[dict[str, AsyncIOMotorClient]] = {}
    con: MongoDsn
    engine_kwargs: dict[str, Any] = Field(default_factory=dict, validate_default=True)
    logger: Logger | None = Field(None, validate_default=True)

    @field_validator("engine_kwargs")
    @classmethod
    def combine_default_kwargs(cls, v: dict):
        return cls.default_engine_kwargs | v

    @field_validator(
        "logger",
    )
    @classmethod
    def set_logger(cls, logger: Logger | None) -> Logger:
        if logger is None:
            logger = logging.getLogger(cls.__name__)
        return logger

    def model_post_init(self, __context: Any) -> None:
        connection_str = self.connection_str
        if connection_str not in self.clients:
            client = MongoClient(connection_str, **self.engine_kwargs)
            self.clients[connection_str] = client

            async_client = AsyncIOMotorClient(connection_str, **self.engine_kwargs)
            self.async_clients[connection_str] = async_client

    @property
    def connection_str(self) -> str:
        return self.con.unicode_string()

    @property
    def client(self) -> MongoClient:
        return self.clients[self.connection_str]

    @property
    def async_client(self) -> AsyncIOMotorClient:
        return self.async_clients[self.connection_str]

    def _describe(self) -> dict[str, Any]:
        return dict(
            con=self.con,
            engine_kwargs=str(self._engine_kwargs),
        )
