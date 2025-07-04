#!/usr/bin/env python3
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

"""
Test runner for the check pipeline integration tests.

This script can be used to run the integration tests independently
or as part of a CI/CD pipeline.
"""

import logging
import sys
from pathlib import Path

# Add the src directory to the Python path (since we're now in src/tests/perfana_ds/)
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_fixture_data_integrity():
    """Test that all fixture data can be loaded correctly."""
    logger.info("=== Testing Fixture Data Integrity ===")

    try:
        from test_check_pipeline_integration import FixtureLoader

        fixture_loader = FixtureLoader()

        # Test loading test run data
        test_run_data = fixture_loader.load_test_run("MyAfterburner-acc-loadTest-00004")
        assert test_run_data["testRunId"] == "MyAfterburner-acc-loadTest-00004"
        logger.info("✅ Test run data loaded successfully")

        # Test loading benchmarks
        benchmarks_data = fixture_loader.load_benchmarks()
        assert len(benchmarks_data) > 0
        logger.info(f"✅ Loaded {len(benchmarks_data)} benchmarks")

        # Test loading dsMetricStatistics
        ds_metrics_data = fixture_loader.load_ds_metric_statistics(
            "MyAfterburner-acc-loadTest-00004"
        )
        assert len(ds_metrics_data) > 0
        logger.info(f"✅ Loaded {len(ds_metrics_data)} dsMetricStatistics documents")

        # Test loading checkResults
        check_results_data = fixture_loader.load_check_results()
        assert len(check_results_data) > 0
        logger.info(f"✅ Loaded {len(check_results_data)} checkResults documents")

        # Test loading compareResults
        compare_results_data = fixture_loader.load_compare_results()
        assert len(compare_results_data) > 0
        logger.info(f"✅ Loaded {len(compare_results_data)} compareResults documents")

        return True

    except Exception as e:
        logger.error(f"❌ Fixture data integrity test failed: {e}")
        return False


def test_pipeline_imports():
    """Test that pipeline modules can be imported."""
    logger.info("=== Testing Pipeline Imports ===")

    try:
        # Test core pipeline imports
        from perfana_ds.pipelines.checks import (
            BenchmarkMatcher,
            DataAggregator,
            RequirementChecker,
            process_single_test_run,
            run_check_pipeline,
        )

        logger.info("✅ Core pipeline modules imported successfully")

        # Test schema imports
        from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
        from perfana_ds.schemas.perfana.benchmarks import Benchmark
        from perfana_ds.schemas.perfana.check_results import CheckResults
        from perfana_ds.schemas.perfana.test_runs import TestRun

        logger.info("✅ Schema modules imported successfully")

        return True

    except ImportError as e:
        logger.error(f"❌ Import test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during import test: {e}")
        return False


def test_schema_validation():
    """Test that fixture data can be validated against schemas."""
    logger.info("=== Testing Schema Validation ===")

    try:
        from test_check_pipeline_integration import FixtureLoader

        from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
        from perfana_ds.schemas.perfana.benchmarks import Benchmark
        from perfana_ds.schemas.perfana.test_runs import TestRun

        fixture_loader = FixtureLoader()

        # Test TestRun schema validation
        test_run_data = fixture_loader.load_test_run("MyAfterburner-acc-loadTest-00004")
        test_run = TestRun(**test_run_data)
        assert test_run.testRunId == "MyAfterburner-acc-loadTest-00004"
        logger.info("✅ TestRun schema validation passed")

        # Test Benchmark schema validation
        benchmarks_data = fixture_loader.load_benchmarks()
        benchmark = Benchmark(**benchmarks_data[0])
        assert benchmark.application == "MyAfterburner"
        logger.info("✅ Benchmark schema validation passed")

        # Test PanelMetricsDocument schema validation
        ds_metrics_data = fixture_loader.load_ds_metric_statistics(
            "MyAfterburner-acc-loadTest-00004"
        )
        panel_metric = PanelMetricsDocument(**ds_metrics_data[0])
        assert (
            panel_metric.testRunId == "MyAfterburner-acc-loadTest-00001"
        )  # Note: fixture data uses different testRunId
        logger.info("✅ PanelMetricsDocument schema validation passed")

        return True

    except Exception as e:
        logger.error(f"❌ Schema validation test failed: {e}")
        return False


def test_mock_catalog_setup():
    """Test that the mock catalog can be set up correctly."""
    logger.info("=== Testing Mock Catalog Setup ===")

    try:
        from test_check_pipeline_integration import FixtureLoader, MockCatalog

        fixture_loader = FixtureLoader()
        mock_catalog = MockCatalog(fixture_loader)

        # Test that mock catalog has required attributes
        assert hasattr(mock_catalog, "testRuns")
        assert hasattr(mock_catalog, "benchmarks")
        assert hasattr(mock_catalog, "dsMetricStatistics")
        assert hasattr(mock_catalog, "checkResults")
        assert hasattr(mock_catalog, "compareResults")

        # Test that mock methods work
        test_run = mock_catalog.testRuns.load_object(
            {"testRunId": "MyAfterburner-acc-loadTest-00004"}
        )
        assert test_run is not None
        assert test_run.testRunId == "MyAfterburner-acc-loadTest-00004"

        benchmarks = mock_catalog.benchmarks.find_objects(
            {
                "application": "MyAfterburner",
                "testType": "loadTest",
                "testEnvironment": "acc",
            }
        )
        assert len(benchmarks) > 0

        logger.info("✅ Mock catalog setup test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Mock catalog setup test failed: {e}")
        return False


def run_quick_integration_test():
    """Run a quick integration test to verify basic functionality."""
    logger.info("=== Running Quick Integration Test ===")

    try:
        from test_check_pipeline_integration import FixtureLoader, MockCatalog

        # Setup
        fixture_loader = FixtureLoader()
        mock_catalog = MockCatalog(fixture_loader)

        # Try to create pipeline components
        from perfana_ds.pipelines.checks import (
            BenchmarkMatcher,
            DataAggregator,
            RequirementChecker,
        )

        benchmark_matcher = BenchmarkMatcher(mock_catalog)
        data_aggregator = DataAggregator(mock_catalog)
        requirement_checker = RequirementChecker(mock_catalog)

        # Load test data
        test_run = mock_catalog.testRuns.load_object(
            {"testRunId": "MyAfterburner-acc-loadTest-00004"}
        )
        benchmarks = mock_catalog.benchmarks.find_objects(
            {
                "application": "MyAfterburner",
                "testType": "loadTest",
                "testEnvironment": "acc",
            }
        )

        logger.info(f"Loaded test run: {test_run.testRunId}")
        logger.info(f"Found {len(benchmarks)} matching benchmarks")

        # Test benchmark matching
        matched_benchmarks = benchmark_matcher.find_matching_benchmarks(test_run)
        logger.info(f"Matched {len(matched_benchmarks)} benchmarks for test run")

        # Test data aggregation for one benchmark
        if matched_benchmarks:
            benchmark = matched_benchmarks[0]
            aggregation_result = data_aggregator.aggregate_metrics_for_benchmark(
                test_run, benchmark
            )
            logger.info(f"Aggregation result keys: {list(aggregation_result.keys())}")

            # Test requirement checking
            check_result = requirement_checker.create_check_result(
                test_run=test_run,
                benchmark=benchmark,
                aggregation_result=aggregation_result,
            )
            logger.info(f"Created check result with status: {check_result.status}")

        logger.info("✅ Quick integration test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Quick integration test failed: {e}")
        logger.exception("Full traceback:")
        return False


def main():
    """Run all validation tests."""
    logger.info("🚀 Starting Check Pipeline Integration Test Validation")

    tests = [
        ("Fixture Data Integrity", test_fixture_data_integrity),
        ("Pipeline Imports", test_pipeline_imports),
        ("Schema Validation", test_schema_validation),
        ("Mock Catalog Setup", test_mock_catalog_setup),
        ("Quick Integration Test", run_quick_integration_test),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")

    logger.info(f"\n🏁 Test Validation Completed: {passed}/{total} tests passed")

    if passed == total:
        logger.info("✅ All validation tests passed! Integration test is ready to run.")
        return 0
    else:
        logger.error("❌ Some validation tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
