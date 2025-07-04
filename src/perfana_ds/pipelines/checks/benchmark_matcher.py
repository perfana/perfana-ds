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

"""Service for matching benchmarks with test runs."""

from perfana_ds.catalog.catalog import Catalog
from perfana_ds.schemas.perfana.benchmarks import Benchmark
from perfana_ds.schemas.perfana.test_runs import TestRun

from .base import BaseCheckService, BenchmarkNotFoundError


class BenchmarkMatcher(BaseCheckService):
    """Service to find matching benchmarks for test runs."""

    def __init__(self, catalog: Catalog):
        super().__init__()
        self.catalog = catalog

    def find_matching_benchmarks(self, test_run: TestRun) -> list[Benchmark]:
        """Find all benchmarks that match the test run criteria.

        Args:
            test_run: The test run to find benchmarks for

        Returns:
            List of matching benchmarks

        Raises:
            BenchmarkNotFoundError: If no matching benchmarks are found
        """
        self.logger.info(
            f"Finding benchmarks for test run {test_run.testRunId} "
            f"(app: {test_run.application}, env: {test_run.testEnvironment}, type: {test_run.testType})"
        )

        # Query benchmarks collection for matches
        filter_criteria = {
            "application": test_run.application,
            "testEnvironment": test_run.testEnvironment,
            "testType": test_run.testType,
        }

        benchmarks = self.catalog.benchmarks.load_objects(filter_criteria)

        if not benchmarks:
            raise BenchmarkNotFoundError(
                f"No benchmarks found for application={test_run.application}, "
                f"testEnvironment={test_run.testEnvironment}, testType={test_run.testType}"
            )

        # Filter out invalid benchmarks
        valid_benchmarks = [b for b in benchmarks if self._is_benchmark_valid(b)]

        self.logger.info(
            f"Found {len(valid_benchmarks)} valid benchmarks (out of {len(benchmarks)} total)"
        )

        return valid_benchmarks

    def find_benchmark_by_id(self, benchmark_id: str) -> Benchmark | None:
        """Find a specific benchmark by ID.

        Args:
            benchmark_id: The benchmark ID to find

        Returns:
            The benchmark if found, None otherwise
        """
        return self.catalog.benchmarks.load_object({"_id": benchmark_id})

    def _is_benchmark_valid(self, benchmark: Benchmark) -> bool:
        """Check if a benchmark is valid for processing.

        Args:
            benchmark: The benchmark to validate

        Returns:
            True if the benchmark is valid, False otherwise
        """
        # Check if benchmark is explicitly marked as invalid
        if benchmark.valid is False:
            self.logger.debug(
                f"Benchmark {benchmark.id} is marked as invalid: {benchmark.reasonNotValid}"
            )
            return False

        # Check if benchmark has required fields
        if not benchmark.panel:
            self.logger.debug(f"Benchmark {benchmark.id} missing panel configuration")
            return False

        # Check if panel has requirement or benchmark configuration
        panel = benchmark.panel
        if not panel.requirement and not panel.benchmark:
            self.logger.debug(
                f"Benchmark {benchmark.id} missing requirement and benchmark configuration"
            )
            return False

        return True

    def process(self, test_run: TestRun) -> list[Benchmark]:
        """Process method implementation for BaseCheckService."""
        return self.find_matching_benchmarks(test_run)
