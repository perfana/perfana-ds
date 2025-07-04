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

"""Schema for applications collection in Perfana."""

from pydantic import BaseModel, Field


class TestType(BaseModel):
    """Test type configuration within a test environment."""

    name: str = Field(description="Name of the test type")
    baselineTestRun: str | None = Field(
        None, description="Baseline test run ID for comparison"
    )
    tags: list[str] | None = Field(
        None, description="Tags associated with this test type"
    )
    differenceScoreThreshold: int | None = Field(
        None, description="Threshold for difference scoring"
    )
    autoCompareTestRuns: bool | None = Field(
        None, description="Whether to automatically compare test runs"
    )
    autoCreateSnapshots: bool | None = Field(
        None, description="Whether to automatically create snapshots"
    )
    enableAdapt: bool | None = Field(None, description="Whether ADAPT is enabled")
    runAdapt: bool | None = Field(None, description="Whether to run ADAPT")
    adaptMode: str | None = Field(None, description="ADAPT mode (e.g., BASELINE)")


class TestEnvironment(BaseModel):
    """Test environment configuration within an application."""

    name: str = Field(description="Name of the test environment")
    testTypes: list[TestType] | None = Field(
        None, description="Test types configured for this environment"
    )


class Application(BaseModel):
    """Application configuration document."""

    id: str | None = Field(None, alias="_id", description="MongoDB document ID")
    name: str = Field(description="Application name")
    description: str | None = Field(None, description="Application description")
    testEnvironments: list[TestEnvironment] | None = Field(
        None, description="Test environments for this application"
    )

    class Config:
        populate_by_name = True
