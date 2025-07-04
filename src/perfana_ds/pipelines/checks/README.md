# Check Pipeline System

A comprehensive pipeline system for processing performance test metrics and evaluating requirements against benchmarks.

## 🎯 Overview

The Check Pipeline system processes dsMetric documents to evaluate performance test results against predefined benchmarks, generating detailed check results and comparison analyses. The system includes advanced features like data quality validation, trend analysis, and performance optimization.

## 📋 Core Components

### 1. **Pipeline Orchestrator** (`pipeline.py`)
- Main entry point for check processing
- Batch processing capabilities
- Error handling and retry logic
- Execution statistics and reporting

### 2. **Benchmark Matching** (`benchmark_matcher.py`)
- Finds relevant benchmarks for test runs
- Supports filtering by application, environment, test type
- Validation and error handling for missing benchmarks

### 3. **Data Aggregation** (`data_aggregator.py`)
- Aggregates dsMetric data using various aggregation types
- Supports ramp-up time filtering
- Pattern matching for target filtering
- Panel averaging calculations

### 4. **Requirement Checking** (`requirement_checker.py`)
- Evaluates requirements against aggregated data
- Advanced operator support (lt, gt, le, ge, eq, ne)
- Default value handling for missing data
- FIT analysis for trend data
- Statistical analysis and quality scoring

### 5. **Benchmark Comparison** (`benchmark_comparison.py`)
- Historical baseline calculation
- Trend analysis and performance comparison
- CompareResults document generation
- Statistical baseline generation (mean, median, std dev)

### 6. **Data Quality Validation** (`data_quality.py`)
- Comprehensive data quality analysis (0.0-1.0 quality scores)
- Artificial data detection
- Outlier identification using IQR method
- Quality reporting with actionable recommendations

### 7. **Performance Optimization** (`performance_optimizer.py`)
- Parallel processing with configurable worker pools
- Batch processing for memory efficiency
- Performance benchmarking and metrics collection
- Database query optimization recommendations

### 8. **Integration Testing** (`integration_tests.py`)
- End-to-end testing suite
- Performance characteristics testing
- Error handling validation
- Data consistency verification

## 🚀 Quick Start

### Basic Usage

```python
from perfana_ds.catalog.catalog import Catalog
from perfana_ds.pipelines.checks.pipeline import run_check_pipeline

# Initialize catalog
catalog = Catalog()

# Process test runs
result = run_check_pipeline(
    test_run_ids=["test_run_123", "test_run_456"],
    catalog=catalog,
    force_reprocess=True
)

print(f"Processed {result['processed_test_runs']} test runs")
print(f"Created {result['created_check_results']} check results")
```

### Enhanced Processing with Quality Validation

```python
from perfana_ds.pipelines.checks.pipeline import process_single_test_run_enhanced
from perfana_ds.pipelines.checks.benchmark_matcher import BenchmarkMatcher
from perfana_ds.pipelines.checks.data_aggregator import DataAggregator
from perfana_ds.pipelines.checks.requirement_checker import RequirementChecker
from perfana_ds.pipelines.checks.benchmark_comparison import BenchmarkComparator
from perfana_ds.pipelines.checks.data_quality import DataQualityValidator

# Initialize services
benchmark_matcher = BenchmarkMatcher(catalog)
data_aggregator = DataAggregator(catalog)
requirement_checker = RequirementChecker(catalog)
benchmark_comparator = BenchmarkComparator(catalog)
data_quality_validator = DataQualityValidator()

# Process with enhanced features
result = process_single_test_run_enhanced(
    test_run=test_run,
    benchmark_matcher=benchmark_matcher,
    data_aggregator=data_aggregator,
    requirement_checker=requirement_checker,
    benchmark_comparator=benchmark_comparator,
    data_quality_validator=data_quality_validator,
    catalog=catalog
)
```

### Performance Optimization

```python
from perfana_ds.pipelines.checks.performance_optimizer import PerformanceOptimizer

# Initialize optimizer
optimizer = PerformanceOptimizer(catalog)

# Run optimized pipeline
result = optimizer.optimize_pipeline_execution(
    test_run_ids=test_run_ids,
    max_workers=4,
    batch_size=10
)

# Get performance insights
metrics = optimizer.get_current_metrics()
recommendations = optimizer.optimize_database_queries()
```

## 📊 Data Flow

```
1. Input: dsMetric documents (from metrics pipeline)
   ↓
2. Benchmark Matching: Find relevant benchmarks
   ↓
3. Data Aggregation: Aggregate metrics with filtering
   ↓
4. Quality Validation: Assess data quality
   ↓
5. Requirement Checking: Evaluate against requirements
   ↓
6. Baseline Comparison: Compare with historical data
   ↓
7. Output: CheckResults & CompareResults documents
```

## 🔧 Configuration

### Aggregation Types

The system supports multiple aggregation types defined in `enums.py`:

- `MIN`: Minimum value
- `MAX`: Maximum value
- `MEAN`: Average value (alias: `AVG`)
- `LAST`: Last recorded value
- `Q10`, `Q25`, `Q75`, `Q90`, `Q95`, `Q99`: Quantiles
- `FIT`: Linear regression fit analysis

### Requirement Operators

Operators for requirement evaluation:

- `LT` / `lt`: Less than
- `GT` / `gt`: Greater than
- `LE` / `le`: Less than or equal
- `GE` / `ge`: Greater than or equal
- `EQ` / `eq`: Equal to
- `NE` / `ne`: Not equal to

### Benchmark Operators

Operators for benchmark comparison:

- `LT`: Current value should be less than baseline
- `GT`: Current value should be greater than baseline
- `ABS`: Absolute difference evaluation

## 📈 Performance Features

### Parallel Processing
- Configurable worker pools for concurrent processing
- Batch processing to manage memory usage
- Automatic optimization based on system resources

### Caching and Optimization
- Database query optimization recommendations
- Performance metrics collection and analysis
- Efficiency scoring for parallel operations

### Monitoring and Metrics
- Execution time tracking
- Success/failure rate monitoring
- Throughput measurement
- Resource usage analysis

## 🧪 Testing

### Integration Tests

Run comprehensive integration tests:

```python
from perfana_ds.pipelines.checks.integration_tests import PipelineIntegrationTester

tester = PipelineIntegrationTester(catalog)
results = tester.run_full_integration_test()

print(f"Test Results: {results['tests_passed']}/{results['tests_run']} passed")
```

### Performance Benchmarks

```python
# Define test scenarios
scenarios = [
    {
        "name": "small_batch",
        "test_run_ids": ["run1", "run2"],
        "max_workers": 2,
        "batch_size": 5
    },
    {
        "name": "large_batch",
        "test_run_ids": ["run1", "run2", "run3", "run4"],
        "max_workers": 4,
        "batch_size": 10
    }
]

# Run benchmarks
benchmark_results = optimizer.benchmark_performance(scenarios)
```

## 🔍 Data Quality Features

### Quality Scoring
- **0.0-1.0 scale**: Comprehensive quality assessment
- **Issue Detection**: Identifies data problems
- **Recommendations**: Actionable improvement suggestions

### Artificial Data Detection
- Pattern recognition for synthetic data
- Default value identification
- Quality degradation alerts

### Outlier Detection
- IQR-based outlier identification
- Statistical analysis of data distributions
- Quality impact assessment

## 📋 Error Handling

### Comprehensive Error Management
- **Graceful Degradation**: System continues processing despite individual failures
- **Detailed Logging**: Comprehensive error tracking and reporting
- **Recovery Mechanisms**: Automatic retry logic for transient failures
- **Validation**: Input validation and data consistency checks

### Error Categories
- **Data Errors**: Missing or invalid metric data
- **Configuration Errors**: Invalid benchmark configurations
- **System Errors**: Database connectivity or resource issues
- **Validation Errors**: Data quality or consistency problems

## 🔄 Pipeline States

### Check Result Status
- `NEW`: Initial state for new check results
- `PASSED`: Requirements met successfully
- `FAILED`: Requirements not met
- `ERROR`: Processing error occurred
- `UNKNOWN`: Unable to determine status

### Processing Flow
1. **Initialization**: Load test run and benchmark data
2. **Validation**: Verify data quality and configuration
3. **Processing**: Execute checks and comparisons
4. **Storage**: Save results to database
5. **Reporting**: Generate execution statistics

## 🏗️ Architecture

### Service-Oriented Design
- **Modular Components**: Independent services for specific functions
- **Dependency Injection**: Services passed as parameters for testability
- **Interface Consistency**: Common base classes and patterns
- **Type Safety**: Pydantic models for data validation

### Database Integration
- **MongoDB Collections**: checkResults and compareResults
- **Efficient Querying**: Optimized queries with proper indexing
- **Upsert Operations**: Conflict resolution for existing documents
- **Transaction Support**: Consistent data operations

## 📚 API Reference

### Main Functions

#### `run_check_pipeline(test_run_ids, catalog, force_reprocess=False)`
Process multiple test runs through the check pipeline.

**Parameters:**
- `test_run_ids`: List of test run IDs to process
- `catalog`: Catalog instance for database access
- `force_reprocess`: Whether to reprocess existing results

**Returns:** Dictionary with processing statistics

#### `process_single_test_run_enhanced(test_run, ...services..., catalog)`
Process a single test run with enhanced features.

**Parameters:**
- `test_run`: TestRun object to process
- Various service instances for processing
- `catalog`: Catalog instance

**Returns:** Dictionary with detailed processing results

### Service Classes

All service classes inherit from `BaseCheckService` and provide:
- Consistent logging interface
- Error handling patterns
- Configuration management
- Performance monitoring

## 🛠️ Development

### Adding New Aggregation Types

1. Add enum value to `AggregationType` in `enums.py`
2. Implement aggregation logic in `DataAggregator._aggregate_values()`
3. Add tests in integration test suite

### Adding New Requirement Operators

1. Add enum value to `RequirementOperator` in `enums.py`
2. Implement evaluation logic in `RequirementChecker._evaluate_enhanced_requirement()`
3. Update documentation and tests

### Extending Data Quality Checks

1. Add new validation method to `DataQualityValidator`
2. Update quality scoring logic
3. Add corresponding tests and documentation

## 🚨 Troubleshooting

### Common Issues

**"No benchmarks found"**
- Verify benchmark configuration matches test run attributes
- Check benchmark active/valid status
- Ensure proper application/environment/testType matching

**"Data quality score too low"**
- Review metric data for missing values
- Check for artificial/default data patterns
- Validate data aggregation logic

**"Performance degradation"**
- Monitor worker pool configuration
- Check database connection pooling
- Review batch size settings
- Analyze performance metrics

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('perfana_ds.pipelines.checks').setLevel(logging.DEBUG)
```

## 📖 Additional Resources

- **Schemas Documentation**: `src/perfana_ds/schemas/perfana/`
- **Catalog Integration**: `src/perfana_ds/catalog/`
- **Example Usage**: See integration tests for practical examples
- **Performance Tuning**: Refer to performance optimizer recommendations

---

**Version**: 1.0.0
**Last Updated**: 2024
**Maintainer**: Perfana DS Team
