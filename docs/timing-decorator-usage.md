# Clean Timing Decorator Usage

This document shows how the simple decorator-based timing approach keeps ETL code clean and readable.

## The Problem with Intrusive Timing

Previously, timing code was scattered throughout the ETL logic:

```python
# ❌ Intrusive approach - clutters the code
def read_data(self):
    start = time.time()

    with TimingContext("File discovery") as discovery_timer:
        # file discovery logic
        pass
    self.detailed_metrics.extract.file_discovery_time = discovery_timer.elapsed

    with TimingContext("File reading") as read_timer:
        # file reading logic
        pass
    self.detailed_metrics.extract.file_read_time = read_timer.elapsed

    self.resource_monitor.sample()
    # ... more timing code mixed with business logic
```

## The Clean Decorator Approach

Now, timing is handled with simple decorators:

```python
# ✅ Clean approach - timing is transparent
@timed_phase("extract")
def read_data(self):
    """Read data based on mode (bulk or incremental)."""
    if self.mode == "bulk":
        self.df = pl.read_parquet(self.input_path)
    else:
        files = self.input_path.glob("incremental_*.parquet")
        self.df = pl.concat([pl.read_parquet(f) for f in files])

    return self.df
```

## How It Works

### 1. Initialize Timer in Constructor

```python
class PolarsPipeline:
    def __init__(self, input_path, output_path, mode):
        # ... other initialization
        self._timer = PipelineTimer(framework="polars", mode=mode)
```

### 2. Decorate Methods

```python
@timed_phase("extract")
def read_data(self):
    # Your business logic here
    pass

@timed_phase("transform", "quality_checks")
def apply_data_quality(self):
    # Your business logic here
    pass

@timed_phase("transform", "sessionization")
def apply_sessionization(self):
    # Your business logic here
    pass

@timed_phase("load", "write")
def write_output(self):
    # Your business logic here
    pass
```

### 3. Start and End Pipeline

```python
def run_pipeline(self):
    self._timer.start_pipeline()

    # Run your ETL steps
    self.read_data()
    self.apply_data_quality()
    self.apply_sessionization()
    self.write_output()

    self._timer.end_pipeline()
    self._timer.log_summary()

    return {"timing_metrics": self._timer.metrics}
```

## What Gets Tracked

The `PipelineTimer` automatically tracks:

- **Startup time**: Framework initialization
- **Extract phase**: Total time for data reading
- **Transform phase**:
  - Quality checks
  - Sessionization
  - Total transform time
- **Load phase**:
  - Merge operations
  - Write operations
  - Total load time
- **Total time**: End-to-end pipeline execution
- **Resource usage**:
  - Peak memory
  - Average memory

## Timing Metrics Structure

```json
{
  "framework": "polars",
  "mode": "bulk",
  "startup_time": 0.05,
  "extract": {
    "total": 1.45,
    "file_discovery": 0.0,
    "file_read": 0.0
  },
  "transform": {
    "total": 2.18,
    "quality_checks": 0.98,
    "sessionization": 1.20
  },
  "load": {
    "total": 1.50,
    "merge": 0.0,
    "write": 1.50
  },
  "total_time": 5.23,
  "resources": {
    "peak_memory_mb": 245.5,
    "avg_memory_mb": 180.3
  }
}
```

## Console Output

```
================================================================================
TIMING SUMMARY - POLARS (bulk)
================================================================================
Total Time: 5.23s
  Startup: 0.05s
  Extract: 1.45s
  Transform: 2.18s
  Load: 1.50s
--------------------------------------------------------------------------------
Peak Memory: 245.50 MB | Avg: 180.30 MB
================================================================================
```

## Benefits

1. **Readable**: Business logic is not cluttered with timing code
2. **Maintainable**: Timing logic is centralized in one place
3. **Consistent**: Same approach works for both Polars and Spark
4. **Simple**: Just add a decorator, no manual timing management
5. **Automatic**: Memory sampling happens automatically
6. **Flexible**: Easy to add new phases or subphases

## Adding New Timed Operations

To add timing to a new operation:

```python
# For a new phase
@timed_phase("new_phase")
def my_new_operation(self):
    # Your code
    pass

# For a subphase
@timed_phase("transform", "my_subphase")
def my_transform_step(self):
    # Your code
    pass
```

## Comparison: Before vs After

### Before (Intrusive)
- 50+ lines of timing code mixed with business logic
- Hard to read and understand the actual ETL flow
- Easy to forget timing instrumentation
- Difficult to maintain

### After (Clean)
- 1 line decorator per method
- Business logic is clear and focused
- Timing is automatic and consistent
- Easy to maintain and extend

## Implementation Details

The decorator works by:

1. Checking if the instance has a `_timer` attribute
2. Recording start time before method execution
3. Executing the actual method
4. Recording elapsed time after method execution
5. Storing timing in the appropriate metrics structure
6. Sampling memory usage automatically

This approach keeps the ETL code clean while still providing comprehensive timing metrics for performance analysis.
