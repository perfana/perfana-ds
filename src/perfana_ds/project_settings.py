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

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="allow"
    )
    PROJECT_NAME: str = "perfana-ds"
    MONGO_URL: str
    MONGO_DB: str = "perfana"
    GRAFANA_URL: str
    GRAFANA_CONCURRENCY: int = 30
    GRAFANA_BATCH_SIZE: int = 20
    DYNATRACE_URL: str | None = None
    DYNATRACE_API_TOKEN: str | None = None
    DYNATRACE_PLATFORM_TOKEN: str | None = None
    MONGO_BATCH_SIZE: int = 100

    @field_validator("GRAFANA_URL", mode="before")
    @classmethod
    def clean_grafana_url(cls, value: str) -> str:
        if value.endswith("/"):
            value = value[:-1]

        return value

    @field_validator("DYNATRACE_URL", mode="before")
    @classmethod
    def clean_dynatrace_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.endswith("/"):
            value = value[:-1]

        return value


def get_settings() -> Settings:
    return Settings()
