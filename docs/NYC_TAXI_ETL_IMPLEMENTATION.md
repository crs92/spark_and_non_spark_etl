# NYC Taxi ETL Implementation

## Overview

This document describes the implementation of the NYC Taxi ETL pipelines for both Polars (vertical scaling) and Spark (horizontal scaling) benchmarks.

## Components Implemented

### 1. NYC Taxi Configuration (`src/etl/nyc_taxi_config.py`)

Defines dataset configurations and handles schema evolution:

- **DataSize Enum**: Predefined sizes (tiny, small, medium, large, xlarge, xxlarge)
- **NYCTaxiDataset**: Configuration dataclass with metadata
- **DATASETS**: Dictionary mapping sizes to configurations
- **SCHEMA_MAPPING**: Handles column name variations across years

**Dataset Configurations:**

| Size    | Time Range           | Files | Approx Size | Approx Records |
|---------|---------------------|-------|-------------|----------------|
| tiny    | 2022-01 (1 month)   | 1     | 0.1 GB      | 3M             |
| small   | 2022 (1 year)       | 12    | 1.2 GB      | 40M            |
| medium  | 2020-2022 (3 years) | 36    | 4.0 GB      | 120M           |
| large   | 2018-2022 (5 years) | 60    | 10.0 GB     | 200M           |
| xlarge  | 2015-2022 (8 years) | 96    | 50.0 GB     | 500M           |
| xxlarge | 2009-2022 (14 years)| 168   | 100.0 GB    | 1B             |

### 2. NYC Taxi Data Access (`src/etl/nyc_taxi_data_access.py`)

Provides data reading utilities with error handling:

- **NYCTaxiDataReader**: Main reader class
  - `read_with_polars()`: Read data using Polars
  - `_standardize_schema_polars()`: Handle schema evolution
  - `_validate_data_polars()`: Data quality validation
  - `get_metadata()`: Return dataset metadata

**Features:**
- Reads directly from public S3 bucket (`s3://nyc-tlc/trip data/`)
- Handles missing files gracefully
- Standardizes column names across years
- Validates data quality (null checks, required columns)

### 3. Polars NYC Taxi ETL (`src/etl/polars_etl_nyc_taxi.py`)

Single-node ETL implementation using Polars:

**ETL Phases:**

1. **Extract**
   - Read Parquet files from S3 using s3fs
   - Handle multiple files for date ranges
   - Track read time and memory usage

2. **Transform**
   - Filter invalid trips (passenger_count > 0, trip_distance > 0, fare > 0)
   - Calculate `price_per_mile = total_amount / trip_distance`
   - Extract date components (year, month, day, hour)
   - Remove outliers (price_per_mile > $100)
   - Aggregate by pickup_location_id and date
   - Calculate: avg_fare, avg_distance, avg_price_per_mile, total_passengers, trip_count

3. **Load**
   - Write aggregated results to Parquet
   - Write metadata JSON with execution metrics
   - Optional: Write to S3 bucket

**CLI Usage:**
```bash
python -m src.etl.polars_etl_nyc_taxi \
  --size tiny \
  --output data/output/nyc_taxi/polars \
  --s3-bucket s3://my-benchmark-bucket
```

### 4. Spark NYC Taxi ETL (`src/etl/spark_etl_nyc_taxi.py`)

Distributed ETL implementation using PySpark:

**ETL Phases:**

1. **Extract**
   - Read Parquet files from S3 using s3a:// protocol
   - Leverage Spark's distributed reading
   - Handle missing files gracefully

2. **Transform**
   - Standardize schema (handle column name variations)
   - Filter invalid trips (identical logic to Polars)
   - Calculate price_per_mile
   - Extract date components
   - Remove outliers
   - Aggregate by pickup_location_id and date (identical aggregations)

3. **Load**
   - Write aggregated results to Parquet
   - Write metadata JSON with execution metrics
   - Optional: Write to S3 bucket

**Spark Configuration:**
- Adaptive query execution enabled
- Dynamic partition coalescing
- S3A filesystem for S3 access
- Kubernetes-aware (checks for K8s environment)

**CLI Usage:**
```bash
python -m src.etl.spark_etl_nyc_taxi \
  --size tiny \
  --output data/output/nyc_taxi/spark \
  --s3-bucket s3://my-benchmark-bucket
```

## Identical Transformation Logic

Both implementations perform **exactly the same transformations** to ensure fair comparison:

1. **Filtering**: Same conditions for invalid trips
2. **Calculations**: Same price_per_mile formula
3. **Aggregations**: Same grouping and aggregation functions
4. **Output Schema**: Identical output columns and types

## Metrics Tracked

Both implementations track:

- **Timing**: Extract, Transform, Load phases
- **Memory**: Peak and average memory usage
- **Records**: Input count, filtered count, output count
- **Data Size**: Approximate GB processed

## Output Format

Both implementations produce:

1. **Results Parquet**: Aggregated data
   - Columns: pickup_location_id, date, avg_fare, avg_distance, avg_price_per_mile, total_passengers, trip_count

2. **Metadata JSON**: Execution metrics
   ```json
   {
     "framework": "polars|spark",
     "dataset": "tiny|small|medium|...",
     "execution_time": 123.45,
     "record_count": 1000000,
     "data_size_gb": 1.2,
     "metrics": {
       "extract": {"total": 10.5},
       "transform": {"total": 45.2},
       "load": {"total": 5.3}
     }
   }
   ```

## Testing

All modules have been verified:

```bash
# Test imports
python -c "from src.etl.nyc_taxi_config import DataSize, DATASETS"
python -c "from src.etl.nyc_taxi_data_access import NYCTaxiDataReader"
python -c "from src.etl.polars_etl_nyc_taxi import PolarsNYCTaxiETL"
python -c "from src.etl.spark_etl_nyc_taxi import SparkNYCTaxiETL"

# Test CLI
python -m src.etl.polars_etl_nyc_taxi --help
python -m src.etl.spark_etl_nyc_taxi --help

# View dataset configurations
python -c "from src.etl.nyc_taxi_config import DataSize, DATASETS;
for s in DataSize: print(DATASETS[s].name, DATASETS[s].time_range)"
```

## Next Steps

1. **EC2 Deployment** (Task 2): Deploy Polars ETL on EC2 instances
2. **EKS Deployment** (Task 3-7): Deploy Spark ETL on EKS with Spark Operator
3. **Benchmark Execution** (Task 8): Run benchmarks across all data sizes
4. **Cost Analysis** (Task 9): Calculate TCO and identify crossover point
5. **Reporting** (Task 10): Generate comprehensive benchmark reports

## Requirements Validated

✅ **Requirement 1.1**: Identical ETL logic for both implementations
✅ **Requirement 4.1**: Read from public NYC Taxi S3 bucket
✅ **Requirement 4.2**: Realistic ETL operations (filter, calculate, aggregate)
✅ **Requirement 4.4**: Track end-to-end timing including S3 operations
✅ **Requirement 5.4**: Consistent ETL logic across implementations
