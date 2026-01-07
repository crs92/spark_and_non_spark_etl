# TPC-H Data Generation Module

This module contains components for generating TPC-H benchmark data at various scale factors.

## Purpose

Generate industry-standard TPC-H benchmark data and write it to S3 in Parquet format with appropriate partitioning.

## Key Components

- **TPCHGenerator**: Main class for generating TPC-H data using DuckDB
- **generate_tpch_data.py**: CLI script for easy data generation
- Data generation utilities
- S3 upload functionality
- Partitioning logic for lineitem table

## Features

- ✅ Generates all 8 TPC-H tables (customer, lineitem, nation, orders, part, partsupp, region, supplier)
- ✅ Supports Scale Factor 10 (~10GB) and Scale Factor 100 (~100GB)
- ✅ Writes directly to S3 in Parquet format with Snappy compression
- ✅ Hive-style partitioning for lineitem table by year/month
- ✅ Progress logging for each table
- ✅ Configurable via environment variables or CLI arguments
- ✅ Context manager support for resource cleanup

## Requirements

### Environment Variables

See `.env.example` for required environment variables:

```bash
# Required
S3_BUCKET_NAME=your-tpch-benchmark-bucket
AWS_REGION=us-east-1

# Optional
PARQUET_COMPRESSION=snappy  # or zstd, gzip
DEBUG=false                  # Enable debug logging
LOG_LEVEL=INFO              # Logging level
```

### AWS Credentials

The generator uses AWS credentials in the following order:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. IAM role (recommended for EC2/ECS/Lambda)
3. AWS credentials file (`~/.aws/credentials`)

## Usage

### Command Line Interface

Generate all tables at Scale Factor 10:

```bash
python -m src.generation.generate_tpch_data --scale-factor 10
```

Generate all tables at Scale Factor 100:

```bash
python -m src.generation.generate_tpch_data --scale-factor 100
```

Generate a specific table only:

```bash
python -m src.generation.generate_tpch_data --scale-factor 10 --table lineitem
```

Specify custom S3 bucket and prefix:

```bash
python -m src.generation.generate_tpch_data \
    --scale-factor 10 \
    --bucket my-custom-bucket \
    --prefix my-custom-prefix
```

Enable verbose logging:

```bash
python -m src.generation.generate_tpch_data --scale-factor 10 --verbose
```

### Python API

```python
from src.generation.tpch_generator import TPCHGenerator

# Initialize generator
generator = TPCHGenerator(
    scale_factor=10,
    s3_bucket="my-bucket",
    s3_prefix="tpch-data"
)

# Generate all tables
generator.generate_all_tables()

# Or generate a specific table
generator.generate_table("customer")

# Generate lineitem with partitioning
generator.generate_table("lineitem", partition_by="l_shipdate")

# Clean up
generator.close()
```

Using context manager (recommended):

```python
from src.generation.tpch_generator import TPCHGenerator

with TPCHGenerator(10, "my-bucket", "tpch-data") as generator:
    generator.generate_all_tables()
# Connection automatically closed
```

## Output Structure

The generator creates the following S3 structure:

```
s3://bucket/tpch-sf10/
  ├── customer/
  │   └── data.parquet
  ├── lineitem/
  │   ├── year=1992/month=01/data.parquet
  │   ├── year=1992/month=02/data.parquet
  │   └── ...
  ├── nation/
  │   └── data.parquet
  ├── orders/
  │   └── data.parquet
  ├── part/
  │   └── data.parquet
  ├── partsupp/
  │   └── data.parquet
  ├── region/
  │   └── data.parquet
  └── supplier/
      └── data.parquet
```

Note: The `lineitem` table is partitioned by year and month for realistic data lake scenarios.

## TPC-H Tables

The generator creates all 8 standard TPC-H tables:

| Table | Rows (SF=10) | Description |
|-------|--------------|-------------|
| customer | 150,000 | Customer information |
| lineitem | 6,000,000 | Order line items (partitioned) |
| nation | 25 | Nation definitions |
| orders | 1,500,000 | Order information |
| part | 200,000 | Part information |
| partsupp | 800,000 | Part supplier relationships |
| region | 5 | Region definitions |
| supplier | 10,000 | Supplier information |

## Performance

Generation times (approximate):

- **SF 10 (~10GB)**: 5-10 minutes
- **SF 100 (~100GB)**: 30-60 minutes

Times vary based on:
- Network bandwidth to S3
- DuckDB performance
- Compression settings

## Troubleshooting

### DuckDB Extension Errors

If you see errors about missing extensions:

```bash
# Install DuckDB extensions manually
python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL tpch'); conn.execute('INSTALL httpfs')"
```

### S3 Permission Errors

Ensure your AWS credentials have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket/*",
        "arn:aws:s3:::your-bucket"
      ]
    }
  ]
}
```

### Memory Issues

For large scale factors (SF 100+), ensure you have sufficient memory:

- Minimum: 8GB RAM
- Recommended: 16GB+ RAM

## Testing

Run unit tests:

```bash
pytest tests/test_tpch_generator.py -v
```

Run with coverage:

```bash
pytest tests/test_tpch_generator.py --cov=src.generation --cov-report=html
```

## Implementation Details

### DuckDB Integration

The generator uses DuckDB's built-in TPC-H extension:

```python
conn.execute("INSTALL tpch")
conn.execute("LOAD tpch")
conn.execute(f"CALL dbgen(sf={scale_factor})")
```

### S3 Direct Write

Data is written directly to S3 without intermediate local storage:

```python
conn.execute(f"""
    COPY {table_name}
    TO 's3://bucket/prefix/{table_name}'
    (FORMAT PARQUET, COMPRESSION 'snappy')
""")
```

### Hive-Style Partitioning

The lineitem table is partitioned by year and month:

```python
conn.execute(f"""
    COPY (
        SELECT
            *,
            YEAR(l_shipdate) as year,
            MONTH(l_shipdate) as month
        FROM lineitem
        ORDER BY l_shipdate  -- CRITICAL: Enables zone map optimization
    )
    TO 's3://bucket/prefix/lineitem'
    (FORMAT PARQUET, PARTITION_BY (year, month), COMPRESSION 'snappy')
""")
```

This creates a structure like: `lineitem/year=1995/month=03/data.parquet`

### Zone Map Optimization

**Important**: The data is sorted by the partition column before writing. This enables DuckDB's zone map optimization, which tracks min/max values in Parquet metadata. This can improve query performance by **30%+ for filtered scans**.

Reference: [Processing 1TB with DuckDB in 30 seconds](https://blog.dataexpert.io/p/i-processed-1-tb-with-duckdb-in-30)

When querying with filters like `WHERE l_shipdate > '1995-03-15'`, DuckDB can skip entire Parquet files by checking the zone map metadata, dramatically reducing I/O.

## References

- [TPC-H Benchmark Specification](http://www.tpc.org/tpch/)
- [DuckDB TPC-H Extension](https://duckdb.org/docs/extensions/tpch.html)
- [DuckDB S3 Integration](https://duckdb.org/docs/extensions/httpfs.html)
