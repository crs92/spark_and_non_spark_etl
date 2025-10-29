# Detailed ETL Timing Specification

## Objective

Track granular timing metrics for each phase of the ETL process to identify performance bottlenecks and generate comprehensive comparison reports.

## Timing Metrics to Track

### 1. Container/Infrastructure Metrics
- **Image Size**: Docker/Podman image size (MB)
- **Image Build Time**: Time to build container image (seconds)
- **Container Startup Time**: Time from `docker run` to process start (seconds)

### 2. Spark-Specific Metrics
- **Spark Session Init**: Time to initialize SparkSession (seconds)
- **JVM Startup**: Time for JVM to start (seconds)
- **Dependency Loading**: Time to load Spark dependencies (seconds)

### 3. ETL Phase Metrics (Both Frameworks)
- **Extract (Read)**: Time to read input data (seconds)
  - File I/O time
  - Data parsing time
  - Schema inference time
- **Transform**: Time for data transformations (seconds)
  - Data quality checks
  - Type casting
  - Sessionization logic
  - Aggregations
- **Load (Write)**: Time to write output (seconds)
  - Data serialization
  - File/table write time
  - Iceberg commit time (if applicable)

### 4. Additional Metrics
- **Memory Usage**: Peak memory consumption (MB)
- **CPU Usage**: Average CPU utilization (%)
- **Records Processed**: Total number of records
- **Data Size**: Input/output data size (MB)
- **Throughput**: Records per second

## Implementation Plan

### Phase 1: Enhanced Timing in ETL Scripts
1. Add detailed timing decorators/context managers
2. Track each ETL phase separately
3. Export timing data to JSON

### Phase 2: Container Metrics Collection
1. Measure image sizes
2. Track build times
3. Monitor container startup overhead

### Phase 3: Comprehensive Report Generation
1. Run benchmarks for small, medium, large datasets
2. Collect all metrics
3. Generate comparison tables and charts
4. Export to JSON, CSV, and Markdown

### Phase 4: Visualization
1. Create timing breakdown charts
2. Generate performance comparison graphs
3. Identify bottlenecks visually

## Expected Output Format

### JSON Structure
```json
{
  "dataset_size": "small",
  "framework": "polars",
  "mode": "bulk",
  "container": {
    "image_size_mb": 450,
    "build_time_s": 45.2,
    "startup_time_s": 0.8
  },
  "etl_phases": {
    "extract": {
      "time_s": 0.19,
      "records": 99574,
      "data_size_mb": 3.6
    },
    "transform": {
      "time_s": 0.28,
      "quality_check_s": 0.11,
      "sessionization_s": 0.10,
      "other_s": 0.07
    },
    "load": {
      "time_s": 0.13,
      "output_size_mb": 3.7,
      "format": "parquet"
    }
  },
  "resources": {
    "peak_memory_mb": 245,
    "avg_cpu_percent": 85,
    "throughput_records_per_sec": 187688
  },
  "total_time_s": 0.60
}
```

### Markdown Report Example
```markdown
# ETL Performance Report

## Small Dataset (100K records)

### Polars (Pythonic)
| Phase | Time (s) | % of Total |
|-------|----------|------------|
| Container Startup | 0.8 | 57% |
| Extract | 0.19 | 13% |
| Transform | 0.28 | 20% |
| Load | 0.13 | 9% |
| **Total** | **1.40** | **100%** |

### Spark
| Phase | Time (s) | % of Total |
|-------|----------|------------|
| Container Startup | 2.5 | 6% |
| Spark Session Init | 15.2 | 36% |
| Extract | 4.1 | 10% |
| Transform | 5.3 | 13% |
| Load | 8.1 | 19% |
| **Total** | **42.2** | **100%** |

### Winner: Polars (30x faster)
```

## Deliverables

1. **Enhanced ETL Scripts**
   - `src/etl/polars_etl.py` with detailed timing
   - `src/etl/spark_etl.py` with detailed timing

2. **Timing Utilities**
   - `src/etl/timing_utils.py` - Timing decorators and helpers

3. **Report Generator**
   - `scripts/generate_performance_report.py` - Comprehensive report generator

4. **Benchmark Runner**
   - `scripts/run_full_benchmark_suite.sh` - Run all sizes and generate reports

5. **Documentation**
   - `docs/performance-analysis.md` - Detailed performance analysis
   - `PERFORMANCE_REPORT.md` - Generated report with all results

## Timeline

- **Phase 1**: Enhanced timing (2-3 hours)
- **Phase 2**: Container metrics (1-2 hours)
- **Phase 3**: Report generation (2-3 hours)
- **Phase 4**: Visualization (optional, 2-3 hours)

**Total**: 5-8 hours of implementation

## Success Criteria

1. ✅ All timing metrics collected accurately
2. ✅ Reports generated for small, medium, large datasets
3. ✅ Clear identification of performance bottlenecks
4. ✅ Actionable insights for optimization
5. ✅ Reproducible benchmarks with consistent results

## Next Steps

1. Implement timing utilities
2. Update ETL scripts with detailed timing
3. Create report generator
4. Run comprehensive benchmark suite
5. Generate and review performance reports

Would you like me to proceed with the implementation?
