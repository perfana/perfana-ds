# Perfana Check System - Functional Specification

## Overview

The Perfana Check system is a comprehensive performance testing and monitoring framework built in Kotlin using Spring Boot and reactive MongoDB. It processes performance test results, evaluates metrics against requirements, and compares test runs with baselines. The system uses MongoDB change streams to react to data changes and process evaluations asynchronously.

## Core Architecture

### Main Components

1. **Event Processors** - React to MongoDB change streams for different document types
2. **Evaluators** - Perform analysis and evaluation logic for different panel types
3. **Services** - Business logic for processing check and compare results
4. **Configuration** - Spring configuration classes for dependency injection

### Technology Stack
- **Language**: Kotlin
- **Framework**: Spring Boot with reactive programming
- **Database**: MongoDB with change streams
- **Logging**: SLF4J with MDC support
- **Metrics Processing**: Time series analysis and statistical evaluation

## Module Structure

### 1. Application Module (`/application`)

**Purpose**: Monitors application dashboard events for deletion tracking

**Components**:
- `ApplicationDashboardEventProcessor`: Processes application dashboard change events
  - Logs errors when dashboards are unexpectedly deleted
  - Extends `AbstractEventProcessor` base class

### 2. Check Result Module (`/checkresult`)

**Purpose**: Evaluates performance metrics against predefined requirements

**Core Components**:

#### CheckResultEventProcessor
- **Functionality**: Main orchestrator for check result processing
- **Event Handling**: Reacts to `CheckResult` document changes
- **Status Flow**: NEW → IN_PROGRESS → COMPLETE/ERROR
- **Key Operations**:
  - Updates orchestrator status
  - Delegates to panel-specific evaluators
  - Handles errors with user-friendly messages
  - Measures processing duration

#### Evaluators
1. **CheckTimeSeriesPanelEvaluator**
   - Evaluates time series data (graphs, stats, single stats)
   - Supports aggregation types: min, max, avg, percentile, fit analysis
   - Handles ramp-up period exclusion
   - Performs linear fit analysis with quality assessment
   - Validates data availability and null value handling

2. **CheckTablePanelEvaluator**
   - Evaluates table panel data
   - Processes tabular metrics and values

#### Configuration
- `TimeSeriesEvaluatorConfig`: Configuration for time series evaluation parameters
- `CheckConfig`: Spring bean configuration mapping panel types to evaluators

### 3. Compare Result Module (`/compareresult`)

**Purpose**: Compares current test results with baseline or previous test runs

**Core Components**:

#### CompareResultEventProcessor
- **Functionality**: Orchestrates comparison processing
- **Support**: Both automated and ad-hoc (manual UI) comparisons
- **Event Handling**: Reacts to `CompareResult` document changes
- **Key Features**:
  - Baseline comparison logic
  - Previous test run comparison
  - Ad-hoc comparison support
  - DSMetric integration for data source metrics

#### Evaluators
1. **CompareTimeSeriesPanelEvaluator** & **CompareTimeSeriesPanelWithDefaultEvaluator**
   - Compare time series between test runs
   - Handle missing data scenarios
   - Support different comparison strategies

2. **CompareTablePanelEvaluator**
   - Compare tabular data between test runs

#### Services
- `CompareResultService`: Business logic for creating and processing compare results

### 4. Test Run Module (`/testrun`)

**Purpose**: Manages test run lifecycle and triggers data processing

**Components**:

#### TestRunEventProcessor
- **Functionality**: Monitors test run status changes
- **Integration**: Calls FastAPI services for data analysis
- **Key Triggers**:
  - Test completion: Triggers `analyzeDataForTestRun`
  - Re-evaluation: Deletes results and calls `reEvaluateChecks`
  - Refresh: Comprehensive re-evaluation with `refreshAll`
  - Adapt re-evaluation: Calls `reEvaluateAdapt`

#### BatchEventProcessor
- Handles batch processing operations for test runs

### 5. DSMetric Module (`/dsmetric`)

**Purpose**: Processes data source metrics and benchmark comparisons

**Components**:

#### DSMetricEventProcessor
- **Functionality**: Processes DSMetric document changes
- **Operations**:
  - Validates benchmark availability
  - Creates check results for panels with requirements
  - Creates compare results for panels with benchmarks
  - Handles error reporting and status updates

#### Supporting Classes
- `DSMetricBenchmarkTestRunData`: Data structure for benchmark test run information
- `DSMetricStatus`: Enumeration for metric processing status
- `DSAdaptConclusionEventProcessor`: Processes adaptation conclusions

### 6. Snapshots Module (`/snapshots`)

**Purpose**: Legacy snapshot event processing (deprecated when FastAPI MongoDB adapter is enabled)

**Components**:
- `SnapshotEventProcessor`: Legacy processor for snapshot-related changes
  - **Note**: Disabled when `fastAPIMongoAdapterConfig.enabled = true`
  - **Modern Approach**: DSMetric processing replaces snapshot-based evaluation

## Core Functionality

### 1. Event Processing Pattern

All processors extend `AbstractEventProcessor` and implement:
```kotlin
override fun handleEvent(event: ChangeStreamEvent<*>)
```

**Common Pattern**:
1. Validate event and extract document
2. Check document status/operation type
3. Route to appropriate processing method
4. Handle errors with logging and user feedback
5. Update orchestrator status

### 2. Panel Type Evaluation System

**Supported Panel Types**:
- `GRAPH`: Time series graphs
- `TIME_SERIES`: Modern time series panels
- `STAT`: Single statistic panels
- `SINGLESTAT`: Legacy single statistic panels
- `TABLE`: Table panels
- `TABLE_OLD`: Legacy table panels

**Evaluation Flow**:
1. **Data Retrieval**: Fetch data from snapshots or data sources
2. **Processing**: Apply ramp-up exclusions, filtering, aggregation
3. **Evaluation**: Compare against requirements or benchmarks
4. **Result Generation**: Create structured results with pass/fail status

### 3. Time Series Analysis Features

#### Data Processing
- **Ramp-up Period**: Exclude initial test period from analysis
- **Null Value Handling**: Support for missing data scenarios
- **Artificial Data**: Generate default values when no data available
- **Aggregation Types**: Min, max, average, percentiles, linear fit

#### Statistical Analysis
- **Linear Fit Analysis**: Trend analysis with quality assessment
- **Quality of Fit**: Statistical validation of fit reliability
- **Percentage Change**: Calculate performance changes over time

#### Requirements Evaluation
- **Operator Support**: Greater than, less than, equals, between
- **Threshold Comparison**: Evaluate metrics against defined limits
- **Boolean Logic**: Combine multiple criteria for overall assessment

### 4. Error Handling and Logging

**Error Categories**:
- `NoDataException`: Missing or insufficient data
- `FitQualityException`: Poor statistical fit quality
- `SnapshotNotFoundException`: Missing dashboard snapshots
- `CheckResultServiceException`: Service-level errors

**Logging Strategy**:
- **MDC Context**: Test run and panel identification
- **Exception References**: Unique error tracking identifiers
- **User-Friendly Messages**: Simplified error descriptions
- **Detailed Logging**: Technical details for debugging

### 5. Status Management

**Result Status Flow**:
```
NEW → IN_PROGRESS → COMPLETE
                 → ERROR
                 → RESTART
```

**Orchestrator Integration**:
- Progress tracking across multiple evaluations
- Test run status coordination
- Error aggregation and reporting

### 6. Configuration Management

**Key Configuration Classes**:
- `CheckConfig`: Panel type to evaluator mapping
- `CheckCompareWatcherConfig`: Feature enablement flags
- `TimeSeriesEvaluatorConfig`: Time series evaluation parameters
- `TestRunProcessorConfig`: Test run processing settings

## Data Flow

### 1. Check Result Processing (Modern DSMetric-based Flow)
```
testRuns Collection (TestRun Completion) → FastAPI Analysis →
dsMetrics Collection (DSMetric Creation with Panel Data) →
benchmarks Collection (Benchmark Validation) →
checkResults Collection (CheckResult Creation & Evaluation) →
checkResults Collection (Status Update) → Orchestrator Notification
```

**MongoDB Collections Involved**:
- **testRuns**: Test run lifecycle and status tracking
- **dsMetrics**: Panel data and metric definitions (replaces snapshot-based retrieval)
- **benchmarks**: Benchmark definitions for requirements
- **checkResults**: Check evaluation results and status

**Legacy Flow (Deprecated)**:
```
testRuns Collection → snapshots Collection → checkResults Collection
```
- **snapshots**: Legacy dashboard snapshot data (only used when FastAPI adapter disabled)

### 2. Compare Result Processing (Modern DSMetric-based Flow)
```
dsMetrics Collection (DSMetric with Benchmark Data) →
benchmarks Collection (Benchmark Configuration) →
testRuns Collection (Previous/Baseline Test Run Selection) →
dsMetrics Collection (Baseline/Previous Data Retrieval) →
Comparison Analysis → Difference Calculation →
compareResults Collection (Result Generation & Status Update)
```

**MongoDB Collections Involved**:
- **dsMetrics**: Current and historical panel data for comparison
- **benchmarks**: Benchmark definitions for comparison criteria
- **testRuns**: Current and baseline test run data
- **compareResults**: Comparison evaluation results and status

**Legacy Flow (Deprecated)**:
```
testRuns Collection → snapshots Collection → compareResults Collection
```
- **snapshots**: Legacy dashboard data (only used when FastAPI adapter disabled)

### 3. DSMetric Processing (Primary Data Flow)
```
dsMetrics Collection (DSMetric Creation with Panel Data) →
benchmarks Collection (Benchmark Validation) →
[If benchmark has requirements] → checkResults Collection (CheckResult Generation) →
[If benchmark has comparison criteria] → compareResults Collection (CompareResult Generation) →
testRuns Collection (Progress Update & Status Tracking)
```

**MongoDB Collections Involved**:
- **dsMetrics**: Data source metric definitions and panel data (primary source)
- **benchmarks**: Benchmark configurations, requirements, and comparison thresholds
- **checkResults**: Generated check evaluations from DSMetrics (when requirements exist)
- **compareResults**: Generated comparison evaluations from DSMetrics (when comparison criteria exist)
- **testRuns**: Test run status and progress tracking
- **dsAdaptConclusion**: Adaptation conclusions and recommendations

**Key Behavior**:
- **CheckResults**: Created only if `benchmark.panel.requirement != null`
- **CompareResults**: Created only if `benchmark.panel.benchmark != null` and test run is not a baseline
- **Parallel Processing**: Both CheckResults and CompareResults can be generated from the same DSMetric

### 4. Application Dashboard Monitoring
```
applicationDashboards Collection (Dashboard Changes) →
Event Processing → Deletion Tracking → Error Logging
```

**MongoDB Collections Involved**:
- **applicationDashboards**: Application dashboard definitions and metadata

### 5. Snapshot Processing (Legacy - Deprecated)
```
snapshots Collection (Snapshot Changes) →
Event Processing → Data Validation → Status Updates
```

**MongoDB Collections Involved**:
- **snapshots**: Dashboard snapshot data and metadata

**Note**: This flow is disabled when `fastAPIMongoAdapterConfig.enabled = true`. The modern approach uses DSMetric processing instead.

### 6. Batch Processing
```
batchProcessEvents Collection (Batch Event Creation) →
Event Processing → Batch Operations → Status Updates
```

**MongoDB Collections Involved**:
- **batchProcessEvents**: Batch processing event definitions and status

## Integration Points

### External Services
- **FastAPI**: Data analysis and processing coordination
- **Grafana**: Dashboard snapshot retrieval
- **MongoDB**: Reactive data storage and change streams

### Internal Dependencies
- **Perfana Engine**: Test run management
- **Orchestrator**: Status coordination and progress tracking
- **Shared Models**: Common data structures and enums

## Key Design Patterns

1. **Event-Driven Architecture**: MongoDB change streams trigger processing
2. **Strategy Pattern**: Panel type-specific evaluators
3. **Template Method**: Common event processing flow with specific implementations
4. **Dependency Injection**: Spring-managed component configuration
5. **Reactive Programming**: Non-blocking asynchronous processing

## Error Recovery and Cleanup

### Cleanup Process (`Cleanup.kt`)
- **Startup Cleanup**: Reset incomplete jobs on system restart
- **Status Recovery**: Convert IN_PROGRESS and NEW to RESTART status
- **Graceful Restart**: Allow reprocessing of interrupted evaluations

### Timeout Handling
- **Processing Timeouts**: Configurable execution time limits
- **Retry Logic**: Automatic retry for transient failures
- **Circuit Breaker**: Prevent cascade failures

## Performance Considerations

### Optimization Features
- **Parallel Processing**: Independent evaluations run concurrently
- **Lazy Loading**: On-demand data retrieval
- **Caching**: Snapshot and benchmark data caching
- **Batch Operations**: Efficient database operations

### Monitoring
- **Execution Time Tracking**: Performance measurement for all operations
- **Progress Indicators**: Real-time status updates
- **Resource Usage**: Memory and CPU monitoring

## Security and Validation

### Input Validation
- **Data Sanitization**: Clean input data for file operations
- **Type Safety**: Strong typing with Kotlin null safety
- **Range Validation**: Bounds checking for numerical inputs

### Error Isolation
- **Exception Boundaries**: Prevent single failure cascade
- **Graceful Degradation**: Continue processing despite individual failures
- **User Feedback**: Clear error messages without technical details
