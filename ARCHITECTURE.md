# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ETL Benchmark System                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
            ┌──────────────────────────────────┐
            │         Benchmark Runner         │
            │    (benchmark_incremental.py)    │
            └─────────────────┬────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
       ┌──────────────────┐        ┌──────────────────┐
       │  Polars Pipeline │        │  Spark Pipeline  │
       │  (polars_etl.py) │        │ (spark_etl_*.py) │
       └────────┬─────────┘        └────────┬─────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  Data Storage  │
                     │   (Parquet)    │
                     └────────────────┘
```

## Incremental Pipeline Steps

```
Step 1: Read CSV
    │
    ├─ Load CSV file
    ├─ Parse headers
    └─ Create DataFrame
    │
    ▼
Step 2: Transform
    │
    ├─ Type casting (timestamp, strings)
    ├─ Data cleaning (remove nulls)
    └─ Basic validation
    │
    ▼
Step 3: Load
    │
    ├─ Write to Parquet
    └─ Optimize storage
    │
    ▼
Step 4: Merge
    │
    ├─ Join with other datasets
    └─ Combine data
    │
    ▼
Step 5: Additional
    │
    ├─ Aggregations
    ├─ Enrichment
    └─ Final transformations
```

## Data Flow

```
Input CSV
    │
    ▼
┌─────────────────┐
│  Step 1: Read   │
│  - Parse CSV    │
│  - Load data    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Step 2:         │
│ Transform       │
│  - Type cast    │
│  - Clean data   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 3: Load   │
│  - Write        │
│    Parquet      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 4: Merge  │
│  - Join data    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Step 5:         │
│ Additional      │
│  - Aggregate    │
│  - Enrich       │
└────────┬────────┘
         │
         ▼
    Output Data
```

## Component Responsibilities

### Data Generation (`src/data_generation/`)
- Generate realistic test data using Faker
- Configurable record count and schema
- Output to CSV format

### Polars ETL (`src/etl/polars_etl.py`)
- Single-node optimized processing
- Lazy evaluation
- Low overhead execution
- Fast for small-medium datasets

### Spark ETL (`src/etl/spark_etl_incremental.py`)
- Distributed processing capability
- Adaptive query execution
- Scalable for large datasets
- Higher startup overhead

### Benchmark Runner (`scripts/benchmark_incremental.py`)
- Execute both pipelines
- Collect timing metrics
- Compare performance
- Generate reports

## Deployment Options

### Local Development
```
Developer Machine
    │
    ├─ Python Environment
    ├─ Polars (pip install)
    └─ PySpark (pip install)
```

### Docker
```
Docker Host
    │
    ├─ Polars Container
    │   └─ Python + Polars
    │
    ├─ Spark Container
    │   └─ PySpark + Java
    │
    └─ Infrastructure
        ├─ MinIO (S3)
        └─ PostgreSQL
```

### Kubernetes
```
K8s Cluster
    │
    ├─ Polars Job
    │   └─ Single Pod
    │
    ├─ Spark Job
    │   ├─ Driver Pod
    │   └─ Executor Pods (N)
    │
    └─ Infrastructure
        ├─ MinIO StatefulSet
        └─ PostgreSQL StatefulSet
```

## Performance Characteristics

### Polars
- **Strengths**: Low overhead, fast single-node, simple deployment
- **Best For**: < 10M records, single machine
- **Startup**: ~0.1s

### Spark
- **Strengths**: Distributed processing, scalability, fault tolerance
- **Best For**: > 10M records, distributed workloads
- **Startup**: ~5-10s

## Technology Stack

- **Python 3.12+**: Primary language
- **Polars**: Single-node DataFrame library
- **PySpark**: Distributed processing framework
- **Faker**: Test data generation
- **Docker**: Containerization
- **Kubernetes**: Orchestration
- **MinIO**: S3-compatible storage
- **PostgreSQL**: Metadata storage

## Metrics Collected

For each pipeline step:
- **Execution Time**: Time to complete step
- **Records Processed**: Number of records
- **Total Time**: End-to-end pipeline time

## Extension Points

### Adding New Steps
1. Add method to pipeline class
2. Update `run_pipeline()` method
3. Add timing metrics
4. Update benchmark script

### Adding New Transformations
1. Modify step methods
2. Keep logic identical across Spark/Polars
3. Test equivalence
4. Benchmark performance

### Adding New Data Sources
1. Update `step_1_read()` method
2. Support new formats (JSON, Avro, etc.)
3. Update tests
4. Document usage
