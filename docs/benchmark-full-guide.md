# Complete ETL Benchmark Guide

## Overview

The complete ETL benchmark (`benchmark_full.py`) runs comprehensive performance comparisons between Polars and Spark ETL stacks across both bulk and incremental processing modes.

## Features

- **Bulk Processing**: Process 30 days of historical data
- **Incremental Processing**: Process 7 days of daily incremental files and merge with bulk data
- **Performance Metrics**: Detailed timing for read, quality checks, sessionization, merge, and write operations
- **Comparative Analysis**: Side-by-side comparison with speedup calculations and winner determination
- **JSON Export**: Complete results saved for further analysis

## Prerequisites

### 1. Generate Test Data

Before running benchmarks, generate the required test data:

```bash
# Generate small dataset (recommended for initial testing)
make generate-data-full SIZE=small

# Generate medium dataset (for more realistic testing)
make generate-data-full SIZE=medium

# Generate large dataset (for production-scale testing)
make generate-data-full SIZE=large
```

This creates:
- `data/generated/bulk/bulk_data_{size}.parquet` - 30 days historical data
- `data/generated/incremental/incremental_*_{size}.parquet` - 7 daily files

### 2. Create Output Directories

```bash
mkdir -p data/output/polars data/output/spark benchmark_results
```

## Usage

### Using Make (Recommended)

```bash
# Run with small dataset (default)
make benchmark-full SIZE=small

# Run with medium dataset
make benchmark-full SIZE=medium

# Run with large dataset
make benchmark-full SIZE=large
```

### Using Python Directly

```bash
# Basic usage
python scripts/benchmark_full.py --size small

# Specify custom output directory
python scripts/benchmark_full.py --size small --output results/

# Get help
python scripts/benchmark_full.py --help
```

## Benchmark Process

The benchmark runs in the following sequence:

1. **Polars Bulk Processing**
   - Reads bulk historical data (30 days)
   - Applies data quality checks
   - Performs sessionization (30-minute inactivity window)
   - Writes output to `data/output/polars/polars_output_bulk.parquet`

2. **Polars Incremental Processing**
   - Reads incremental daily files (7 days)
   - Applies data quality checks
   - Merges with bulk data
   - Re-applies sessionization to merged data
   - Writes output to `data/output/polars/polars_output_incremental.parquet`

3. **Spark Bulk Processing**
   - Same operations as Polars bulk processing
   - Writes output to `data/output/spark/spark_output_bulk.parquet`

4. **Spark Incremental Processing**
   - Same operations as Polars incremental processing
   - Writes output to `data/output/spark/spark_output_incremental.parquet`

5. **Comparison Analysis**
   - Compares bulk processing performance
   - Compares incremental processing performance
   - Calculates overall winner and speedup metrics

## Output

### Console Output

The benchmark prints a detailed comparison table:

```
================================================================================
COMPLETE ETL BENCHMARK RESULTS
================================================================================
Data Size: small
Timestamp: 2025-10-28T12:39:32.123456
================================================================================

--------------------------------------------------------------------------------
BULK PROCESSING (30 days historical data)
--------------------------------------------------------------------------------
Metric                                   Polars               Spark
--------------------------------------------------------------------------------
Total Time (s)                           3.82                 95.43
Records Processed                        99,574               99,574

✓ Winner: POLARS (24.96x faster, 96.0% advantage)

--------------------------------------------------------------------------------
INCREMENTAL PROCESSING (7 days daily files + merge)
--------------------------------------------------------------------------------
Metric                                   Polars               Spark
--------------------------------------------------------------------------------
Total Time (s)                           3.38                 29.91
Records Processed                        106,146              106,234

✓ Winner: POLARS (8.84x faster, 88.7% advantage)

--------------------------------------------------------------------------------
TOTAL PERFORMANCE (Bulk + Incremental)
--------------------------------------------------------------------------------
Framework                                Total Time (s)
--------------------------------------------------------------------------------
Polars                                   7.20
Spark                                    125.34

✓ Overall Winner: POLARS (17.56x faster, 94.3% advantage)

================================================================================
```

### JSON Results

Results are saved to `benchmark_results/benchmark_full_{size}_{timestamp}.json`:

```json
{
  "metadata": {
    "data_size": "small",
    "timestamp": "2025-10-28T12:39:32.123456",
    "total_benchmark_time": 132.54
  },
  "polars": {
    "bulk": {
      "mode": "bulk",
      "total_time": 3.82,
      "metrics": {
        "read_time": 0.76,
        "quality_check_time": 0.33,
        "sessionization_time": 0.26,
        "merge_time": 0.0,
        "write_time": 0.16
      },
      "records_processed": 99574,
      "output_file": "data/output/polars/polars_output_bulk.parquet"
    },
    "incremental": { ... }
  },
  "spark": { ... },
  "comparison": {
    "bulk_processing": {
      "polars_time": 3.82,
      "spark_time": 95.43,
      "winner": "polars",
      "speedup": 24.96,
      "advantage_pct": 96.0
    },
    "incremental_processing": { ... },
    "total_performance": { ... }
  }
}
```

## Performance Insights

### Small Dataset Results (100K records)

- **Polars**: ~7 seconds total (bulk + incremental)
- **Spark**: ~125 seconds total (bulk + incremental)
- **Winner**: Polars (17-25x faster)
- **Key Insight**: Spark's JVM startup overhead dominates for small datasets

### Expected Results by Size

| Dataset | Records | Polars Time | Spark Time | Winner |
|---------|---------|-------------|------------|--------|
| Small   | 100K    | ~7s         | ~125s      | Polars (17x) |
| Medium  | 10M     | ~2-5min     | ~5-10min   | Polars (2-3x) |
| Large   | 100M+   | ~20-30min   | ~15-25min  | Spark (distributed) |

### When to Use Each Stack

**Use Polars when:**
- Dataset fits in memory (< 10GB)
- Single-node processing is sufficient
- Fast iteration and development speed is important
- Minimal infrastructure overhead is desired

**Use Spark when:**
- Dataset exceeds single-node memory (> 50GB)
- Distributed processing is required
- Integration with Hadoop ecosystem is needed
- Fault tolerance for long-running jobs is critical

## Troubleshooting

### Error: Input file not found

```
ERROR:__main__:Input file not found: data/generated/bulk/bulk_data_medium.parquet
INFO:__main__:Please run: make generate-data-full SIZE=medium
```

**Solution**: Generate the required test data first:
```bash
make generate-data-full SIZE=medium
```

### Error: Bulk data not found (during incremental processing)

```
ERROR:__main__:Bulk data not found: data/output/polars/polars_output_bulk.parquet
INFO:__main__:Please run bulk processing first
```

**Solution**: The benchmark automatically runs bulk processing first, but if you're running incremental processing separately, ensure bulk processing completed successfully.

### Spark Warnings

Spark may show warnings like:
```
WARN Utils: Your hostname resolves to a loopback address
WARN NativeCodeLoader: Unable to load native-hadoop library
```

These are normal and don't affect benchmark results. They indicate Spark is running in local mode without native optimizations.

## Advanced Usage

### Running Individual Modes

You can run bulk or incremental processing separately:

```bash
# Polars bulk only
python -m src.etl.polars_etl --mode bulk --input data/generated/bulk/bulk_data_small.parquet

# Polars incremental only (requires bulk data first)
python -m src.etl.polars_etl --mode incremental --input data/generated/incremental

# Spark bulk only
python -m src.etl.spark_etl --mode bulk --input data/generated/bulk/bulk_data_small.parquet

# Spark incremental only (requires bulk data first)
python -m src.etl.spark_etl --mode incremental --input data/generated/incremental
```

### Analyzing Results

Use `jq` to analyze JSON results:

```bash
# Get total times
jq '.comparison.total_performance' benchmark_results/benchmark_full_small_*.json

# Get bulk processing winner
jq '.comparison.bulk_processing.winner' benchmark_results/benchmark_full_small_*.json

# Get detailed metrics
jq '.polars.bulk.metrics' benchmark_results/benchmark_full_small_*.json
```

## Related Commands

- `make generate-data-full SIZE=small` - Generate test data
- `make benchmark` - Run incremental benchmark only
- `python scripts/benchmark.py` - Run Docker-based benchmark
- `python scripts/benchmark_incremental.py` - Run staged pipeline benchmark

## Requirements Satisfied

This benchmark satisfies the following requirements:

- **3.1**: Generate detailed performance reports with visualizations
- **3.2**: Identify clear use cases where each technology stack excels
- **5.1**: Allow adjustment of data size, complexity, and processing parameters
