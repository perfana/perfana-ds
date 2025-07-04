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

"""Base classes and utilities for the check pipeline."""

import logging

logger = logging.getLogger(__name__)


class BaseCheckService:
    """Base class for all check pipeline services."""

    def __init__(self):
        self.logger = logger


class CheckPipelineError(Exception):
    """Custom exception for check pipeline errors."""

    pass


class BenchmarkNotFoundError(CheckPipelineError):
    """Raised when no matching benchmark is found."""

    pass


class DataAggregationError(CheckPipelineError):
    """Raised when data aggregation fails."""

    pass


class RequirementCheckError(CheckPipelineError):
    """Raised when requirement checking fails."""

    pass
