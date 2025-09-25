# Clickstream Data Generator

Simple data generator for ETL benchmarking that creates realistic clickstream data with bulk load and incremental files.

## What it generates

The generator creates a folder structure with:
- **Bulk data**: Large historical dataset (30 days of data)
- **Incremental data**: Daily files for testing incremental ETL processes

## Data Schema

Each clickstream event contains:
- `event_id`: Unique event identifier
- `user_id`: User identifier
- `session_id`: Session identifier
- `timestamp`: Event timestamp
- `page_url`: Visited page URL
- `country`: User country code
- `device`: Device type (desktop/mobile/tablet)
- `ip_address`: User IP address

## Usage

### Basic Usage

```python
from src.data_generation import generate_benchmark_data

# Generate small dataset with bulk + 7 days of incremental data
result = generate_benchmark_data(
    size="small",           # small/medium/large
    output_dir="data/test", # Output directory
    formats=["csv", "parquet"],  # File formats
    seed=42,                # For reproducible data
    incremental_days=7      # Number of daily incremental files
)

print(f"Generated {result['bulk_record_count']} bulk records")
print(f"Generated {result['incremental_days']} daily incremental files")
```

### Data Sizes

- **Small**: ~100K records (good for development/testing)
- **Medium**: ~10M records (realistic production size)
- **Large**: ~100M records (stress testing)

### Output Structure

```
data/test/
├── bulk/
│   ├── bulk_data_small.csv
│   └── bulk_data_small.parquet
└── incremental/
    ├── incremental_2024-02-01_small.csv
    ├── incremental_2024-02-01_small.parquet
    ├── incremental_2024-02-02_small.csv
    └── ...
```

### Advanced Usage

```python
from src.data_generation import ClickstreamDataGenerator, DataSize
from datetime import datetime

# Direct generator usage for custom scenarios
generator = ClickstreamDataGenerator(DataSize.SMALL, seed=42)

# Generate bulk historical data
bulk_events = generator.generate_bulk_data(
    start_date=datetime(2024, 1, 1),
    days=30
)

# Generate incremental data for specific date
daily_events = generator.generate_incremental_data(
    date=datetime(2024, 2, 1),
    records_per_day=1000
)
```

## Use Cases

This generator is perfect for:
- **ETL Performance Testing**: Compare Spark vs Python-native processing
- **Pipeline Development**: Test with realistic data volumes
- **Incremental Processing**: Test daily batch processing scenarios
- **Format Comparison**: Compare CSV vs Parquet performance

## Features

- **Reproducible**: Same seed generates identical data
- **Scalable**: Handles small to very large datasets
- **Realistic**: Uses Faker for realistic IP addresses and data patterns
- **Simple**: Focused on ETL needs, no unnecessary complexity
- **Fast**: Efficient generation using Polars DataFrames
