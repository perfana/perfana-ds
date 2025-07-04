# Perfana DS Integration Tests

This directory contains comprehensive integration tests for the Perfana Data Science check pipeline using real fixture data from production test runs.

## 🎯 Test Objectives

These tests validate the complete check pipeline workflow:

1. **Fixture Data Integrity**: Ensures all JSON fixture files are valid and loadable
2. **Data Structure Validation**: Validates that fixture data has the expected schema structure
3. **Benchmark Filtering Logic**: Tests filtering benchmarks by application, test type, and environment
4. **Data Consistency**: Verifies consistency across different fixture data types
5. **Mock Catalog Operations**: Tests CRUD operations on check results, compare results, and test runs
6. **End-to-End Pipeline Simulation**: **NEW** ✨ Complete simulation of the check pipeline workflow using fixture data
7. **Standalone Integrity Test**: Independent validation that can run without pytest

## 📁 Directory Structure

```
src/tests/
├── test_check_pipeline_integration.py    # Main integration tests
├── fixture/                              # Test fixture data
│   ├── benchmarks/                      # 8 benchmark configuration files
│   ├── checkResults/                    # 7 expected check result files
│   ├── compareResults/                  # 14 expected compare result files
│   ├── dsMetricStatistics/              # 20 metric statistics from real test run
│   └── testRun/                         # 1 test run configuration file
└── README.md                            # This documentation
```

## 🔍 Fixture Data Details

### Benchmarks (8 files)
Real benchmark configurations from MyAfterburner application covering:
- **Hikari Connection Pool**: Database connection monitoring
- **Gatling Load Testing**: Response times, failed requests, percentages
- **JFR Exporter**: CPU monitoring via Java Flight Recorder
- **Docker Container Metrics**: Container CPU usage

### dsMetricStatistics (20 records)
Complete metric statistics from testRunId `MyAfterburner-acc-loadTest-00004` including:
- **JFR CPU metrics**: `max_jvmSystem`, `cpu_system`, `cpu_machine_total`
- **Database metrics**: `employee-db-pool` (Hikari Connection Pool)
- **Load testing metrics**: Response times (50th/99th percentile), failed requests
- **Memory management**: JVM G1GC allocation failure metrics

### CheckResults (7 files)
Expected check results for requirement validation covering multiple dashboard/panel combinations.

### CompareResults (14 files)
Expected comparison results for benchmark validation against baseline test runs.

### TestRun (1 file)
Complete test run configuration for `MyAfterburner-acc-loadTest-00004`.

## 🧪 Test Architecture

### FixtureLoader Class
- Loads JSON fixture data from organized directory structure
- Handles missing files gracefully with informative error messages
- Supports loading by specific test run ID

### MockCatalog Class
- Replaces MongoDB catalog with fixture data for testing
- Tracks all CRUD operations (create check results, compare results, update test runs)
- Provides filtering methods that mimic real catalog behavior

### Integration Test Methods

1. **`test_fixture_data_loading`**: Validates all fixture files load correctly
2. **`test_data_structure_validation`**: Ensures proper schema compliance
3. **`test_benchmark_filtering_logic`**: Tests filtering by application parameters
4. **`test_data_consistency_across_fixtures`**: Verifies consistency across fixture types
5. **`test_mock_catalog_operations`**: Tests CRUD operations
6. **`test_end_to_end_fixture_to_schema_validation`** ✨: **Complete pipeline simulation**

### End-to-End Pipeline Simulation ✨

The new `test_end_to_end_fixture_to_schema_validation` test provides comprehensive validation:

**Pipeline Workflow Simulation:**
1. **Data Loading**: Loads all fixture data (benchmarks, metrics, expected results)
2. **TestRun Validation**: Validates test run configuration integrity
3. **Metric Mapping**: Maps dsMetricStatistics to benchmarks using dashboard/panel matching
4. **Panel Title Normalization**: Handles ID prefix differences (e.g., "19-Pending connections" → "Pending connections")
5. **Check Result Generation**: Simulates requirement evaluation with various operators (`lt`, `gt`, `le`, `ge`, `eq`)
6. **Aggregation Logic**: Implements `avg`, `max`, `min` evaluation types from benchmark configuration
7. **Compare Result Generation**: Simulates baseline comparison with percentage calculations
8. **Benchmark Evaluation**: Tests benchmark operators (`pst`, `plt`, `lt`, `gt`)
9. **Data Validation**: Compares generated results against expected fixture data
10. **Catalog Integration**: Validates mock catalog tracks all operations correctly

**Real-World Accuracy:**
- Uses actual production data from `MyAfterburner-acc-loadTest-00004`
- Handles missing requirements/benchmarks gracefully
- Implements realistic aggregation logic based on `evaluateType`
- Validates 8/8 benchmarks find corresponding metrics
- Generates 8 check results and 7 compare results
- Tests against 7 expected check results and 14 expected compare results

## 🚀 Running the Tests

### Run All Integration Tests
```bash
python -m pytest src/tests/test_check_pipeline_integration.py -v --override-ini="addopts="
```

### Run Specific Test
```bash
# End-to-end pipeline simulation
python -m pytest src/tests/test_check_pipeline_integration.py::TestCheckPipelineIntegration::test_end_to_end_fixture_to_schema_validation -v --override-ini="addopts=" -s

# Data integrity only
python -m pytest src/tests/test_check_pipeline_integration.py::test_fixture_data_integrity -v --override-ini="addopts="
```

### Run Standalone Validation
```bash
cd src/tests
python test_check_pipeline_integration.py
```

## 📊 Test Results

**Current Status**: ✅ **All 7 tests passing**

```
✅ test_fixture_data_loading
✅ test_data_structure_validation
✅ test_benchmark_filtering_logic
✅ test_data_consistency_across_fixtures
✅ test_mock_catalog_operations
✅ test_end_to_end_fixture_to_schema_validation
✅ test_fixture_data_integrity
```

**End-to-End Test Summary:**
- ✅ Processed 8 benchmarks
- ✅ Found metrics for 8/8 benchmarks (100% coverage)
- ✅ Generated 8 check results
- ✅ Generated 7 compare results
- ✅ Validated against 7 expected check results
- ✅ Validated against 14 expected compare results
- ✅ Fast execution (~0.05 seconds for all tests)

## 🔧 Key Technical Features

### Smart Panel Title Matching
The test handles real-world data inconsistencies where benchmark panel titles include ID prefixes:
- **Benchmark**: `"19-Pending connections"`
- **Metric**: `"Pending connections"`
- **Solution**: `_clean_panel_title()` method normalizes for matching

### Robust Error Handling
- Handles missing `requirement` and `benchmark` configurations gracefully
- Provides detailed debugging output showing which benchmarks have matching metrics
- Fails fast with informative error messages

### Real Production Data
- Uses actual dsMetricStatistics from live Perfana database
- Covers diverse metric types: CPU, memory, database, load testing
- Includes edge cases like metrics without requirements

## 🎯 Next Steps

The integration tests now provide a solid foundation for:

1. **Pipeline Development**: Safe refactoring with comprehensive test coverage
2. **Data Validation**: Ensuring fixture data represents real-world scenarios
3. **Regression Testing**: Detecting changes in pipeline behavior
4. **Performance Testing**: Baseline for optimization efforts
5. **Documentation**: Living examples of expected data structures and workflows

## 🛠️ Troubleshooting

### Common Issues

**Import Errors**: Ensure you're running from the correct directory and using `--override-ini="addopts="`

**Missing Fixtures**: Verify all fixture files exist in the correct directory structure

**Data Mismatches**: Check that panel titles match between benchmarks and metrics (with ID prefix normalization)

**Python Version**: Tests require Python 3.9+ (avoiding Python 3.10+ union syntax issues)

## 🔗 Related Files

- **Pipeline Source**: `src/perfana_ds/pipelines/`
- **Schema Definitions**: `src/perfana_ds/schemas/perfana/`
- **Production Database**: MongoDB collections (`benchmarks`, `dsMetricStatistics`, `checkResults`, `compareResults`, `testRuns`)

---

*Last updated: 2025-01-28 - Added comprehensive end-to-end pipeline simulation test*
