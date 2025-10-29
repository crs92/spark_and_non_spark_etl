# Iceberg Table Implementation

## Overview

Both Polars and Spark ETL pipelines now support Apache Iceberg tables for proper data warehouse operations with:

- **Bulk Mode**: Initial load with table creation/overwrite
- **Incremental Mode**: Merge/upsert operations based on primary key (event_id)

## Architecture

### Local Iceberg Catalog

- **Type**: SQLite-based catalog for local development
- **Location**: `data/iceberg_warehouse/`
- **Catalog DB**: `data/iceberg_warehouse/catalog.db`
- **Table Data**: `data/iceberg_warehouse/etl/clickstream_events/data/`

### Table Schema

```
etl.clickstream_events
├── event_id (string, required) - Primary Key
├── user_id (string, required)
├── session_id (string, optional)
├── timestamp (timestamp, required)
├── page_url (string, optional)
├── country (string, optional)
├── device (string, optional)
├── ip_address (string, optional)
├── session_start (timestamp, optional)
├── session_end (timestamp, optional)
└── session_duration_minutes (double, optional)
```

## Polars ETL with Iceberg

### Implementation Details

- **Library**: PyIceberg (Python-native Iceberg client)
- **Catalog**: SQLite-based local catalog
- **Bulk Write**: Uses `table.overwrite()` to replace all data
- **Incremental Merge**:
  1. Read existing data from Iceberg table
  2. Combine with new data
  3. Deduplicate by event_id (keeping latest)
  4. Overwrite table with merged data

### Usage

```bash
# Bulk mode (create/overwrite table)
.venv/bin/python -m src.etl.polars_etl --mode bulk \
  --input data/generated/bulk/bulk_data_small.parquet

# Incremental mode (merge/upsert)
.venv/bin/python -m src.etl.polars_etl --mode incremental \
  --input data/generated/incremental

# Disable Iceberg (use Parquet files)
.venv/bin/python -m src.etl.polars_etl --mode bulk \
  --input data/generated/bulk/bulk_data_small.parquet \
  --no-iceberg
```

### Performance

**Small Dataset (100K records)**:
- Bulk write: ~0.4s
- Incremental merge: ~2.2s (includes reading 100K existing records)

## Spark ETL with Iceberg

### Implementation Details

- **Library**: Iceberg Spark Runtime (iceberg-spark-runtime-4.0_2.13)
- **Catalog**: Hadoop catalog with file-based warehouse
- **Bulk Write**: Uses `writeTo().createOrReplace()`
- **Incremental Merge**: Uses SQL `MERGE INTO` statement
  ```sql
  MERGE INTO local.etl.clickstream_events AS target
  USING new_data AS source
  ON target.event_id = source.event_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
  ```

### Usage

```bash
# Bulk mode (create/overwrite table)
.venv/bin/python -m src.etl.spark_etl --mode bulk \
  --input data/generated/bulk/bulk_data_small.parquet

# Incremental mode (merge/upsert)
.venv/bin/python -m src.etl.spark_etl --mode incremental \
  --input data/generated/incremental

# Disable Iceberg (use Parquet files)
.venv/bin/python -m src.etl.spark_etl --mode bulk \
  --input data/generated/bulk/bulk_data_small.parquet \
  --no-iceberg
```

### Performance

**Small Dataset (100K records)**:
- Bulk write: ~37s (includes Spark startup overhead)
- Incremental merge: ~38s (includes merge operation)

## Key Features

### 1. Proper ETL Phases

✅ **Extract**: Read from source files (CSV/Parquet)
✅ **Transform**: Data quality checks, type casting, sessionization
✅ **Load**: Write to Iceberg tables with proper merge operations

### 2. Bulk Processing

- Initial data load (30 days historical)
- Creates or replaces Iceberg table
- Overwrites all existing data
- Fast for initial setup

### 3. Incremental Processing

- Daily incremental files (7 days)
- Merge/upsert based on primary key (event_id)
- Handles both INSERT (new records) and UPDATE (existing records)
- Maintains data consistency

### 4. ACID Transactions

Iceberg provides:
- **Atomicity**: All-or-nothing writes
- **Consistency**: Schema evolution and validation
- **Isolation**: Concurrent reads during writes
- **Durability**: Metadata versioning and snapshots

## Verification

### Check Iceberg Catalog

```bash
# View catalog database
sqlite3 data/iceberg_warehouse/catalog.db ".tables"

# View table metadata
sqlite3 data/iceberg_warehouse/catalog.db "SELECT * FROM iceberg_tables;"
```

### Check Table Data

```bash
# List data files
find data/iceberg_warehouse/etl/clickstream_events/data -name "*.parquet"

# Count records using Polars
.venv/bin/python -c "
import polars as pl
from pyiceberg.catalog import load_catalog

config = {
    'type': 'sql',
    'uri': 'sqlite:///data/iceberg_warehouse/catalog.db',
    'warehouse': 'file://$(pwd)/data/iceberg_warehouse'
}
catalog = load_catalog('local', **config)
table = catalog.load_table('etl.clickstream_events')
scan = table.scan()
df = pl.from_arrow(scan.to_arrow())
print(f'Total records: {len(df):,}')
"
```

### Query Table with Spark

```bash
.venv/bin/python -c "
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .config('spark.sql.extensions', 'org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions')
    .config('spark.sql.catalog.local', 'org.apache.iceberg.spark.SparkCatalog')
    .config('spark.sql.catalog.local.type', 'hadoop')
    .config('spark.sql.catalog.local.warehouse', 'file://$(pwd)/data/iceberg_warehouse')
    .getOrCreate())

df = spark.table('local.etl.clickstream_events')
print(f'Total records: {df.count():,}')
df.show(5)
spark.stop()
"
```

## Dependencies

### Python Packages

```toml
dependencies = [
    "polars",
    "pyarrow",
    "pyiceberg[sql-sqlite]",  # PyIceberg with SQLite support
    "duckdb",
    "pyspark",
    "faker",
]
```

### Spark JARs

Iceberg Spark runtime JAR is required:

```bash
# Download for Spark 4.0
spark-shell --packages org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:1.6.1

# JAR location
~/.ivy2/cache/org.apache.iceberg/iceberg-spark-runtime-4.0_2.13/jars/
```

## Comparison: Polars vs Spark with Iceberg

| Feature | Polars + PyIceberg | Spark + Iceberg |
|---------|-------------------|-----------------|
| **Bulk Write** | 0.4s | 37s |
| **Incremental Merge** | 2.2s | 38s |
| **Merge Strategy** | Manual (read + dedupe + overwrite) | Native SQL MERGE |
| **Catalog Type** | SQLite | Hadoop |
| **Startup Overhead** | Minimal | High (JVM + Spark) |
| **Memory Usage** | Low | High |
| **Best For** | Single-node, fast iteration | Distributed, large-scale |

## Advantages of Iceberg

### vs Parquet Files

1. **ACID Transactions**: Atomic writes, no partial failures
2. **Schema Evolution**: Add/remove columns without rewriting data
3. **Time Travel**: Query historical snapshots
4. **Partition Evolution**: Change partitioning without rewriting
5. **Hidden Partitioning**: Automatic partition management
6. **Concurrent Writes**: Multiple writers without conflicts

### vs Traditional Databases

1. **Open Format**: Not locked to specific vendor
2. **Cloud Native**: Works with S3, ADLS, GCS
3. **Separation of Compute/Storage**: Scale independently
4. **Query Engine Agnostic**: Works with Spark, Trino, Flink, etc.

## Troubleshooting

### PyIceberg: SQLAlchemy not found

```bash
# Install with SQLite support
uv pip install 'pyiceberg[sql-sqlite]'
```

### Spark: Iceberg extensions not found

```bash
# Ensure correct JAR version for your Spark version
find ~/.ivy2 -name "*iceberg-spark-runtime*.jar"

# Download if missing
spark-shell --packages org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:1.6.1
```

### Schema Mismatch Errors

Ensure required fields (event_id, user_id, timestamp) are non-nullable:
```python
# Polars automatically handles this in _write_to_iceberg()
# Spark requires proper schema definition
```

### Merge Performance

For large incremental merges:
- Consider partitioning by date
- Use predicate pushdown in merge conditions
- Monitor snapshot growth and compact regularly

## Future Enhancements

1. **Partitioning**: Partition by date for better query performance
2. **Compaction**: Automatic small file compaction
3. **Snapshot Management**: Expire old snapshots to save space
4. **Metadata Tables**: Query table history and snapshots
5. **S3/MinIO Support**: Use object storage instead of local files
6. **Distributed Catalog**: Use Hive Metastore or Nessie for production
