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

"""Check pipeline for processing dsMetric documents and generating checkResult documents."""

from .base import (
    BaseCheckService,
    BenchmarkNotFoundError,
    CheckPipelineError,
    DataAggregationError,
    RequirementCheckError,
)
from .benchmark_comparison import BenchmarkComparator
from .benchmark_matcher import BenchmarkMatcher
from .data_aggregator import DataAggregator
from .pipeline import process_single_test_run, run_check_pipeline
from .requirement_checker import RequirementChecker

__all__ = [
    # Core pipeline functions
    "run_check_pipeline",
    "process_single_test_run",
    # Core services
    "BenchmarkMatcher",
    "DataAggregator",
    "RequirementChecker",
    "BenchmarkComparator",
    # Base classes and exceptions
    "BaseCheckService",
    "CheckPipelineError",
    "BenchmarkNotFoundError",
    "DataAggregationError",
    "RequirementCheckError",
]
