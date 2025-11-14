# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│              ETL Performance Benchmark System               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
            ┌──────────────────────────────────┐
            │      Benchmark Orchestration     │
            │   (benchmark_full.py / Make)     │
            └─────────────────┬────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
       ┌──────────────────┐        ┌──────────────────┐
       │  Polars Pipeline │        │  Spark Pipeline  │
       │  (polars_etl.py) │        │  (spark_etl.py)  │
       │  + Timing        │        │  + Timing        │
       └────────┬─────────┘        └────────┬─────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌──────────────────────────┐
                │   Performance Analysis   │
                │  - JSON Reports          │
                │  - Timing Metrics        │
                │  - PowerPoint Generation │
                └──────────────────────────┘
```

## ETL Pipeline Phases

```
Phase 1: EXTRACT
    │
    ├─ File Discovery
    ├─ File Reading (CSV/Parquet)
    └─ Schema Inference
    │
    ▼
Phase 2: TRANSFORM
    │
    ├─ Data Quality Checks
    │   ├─ Type Casting
    │   ├─ Null Handling
    │   └─ Deduplication
    │
    ├─ Sessionization
    │   ├─ Sort by user + timestamp
    │   ├─ Calculate time gaps
    │   ├─ Identify session boundaries (30min)
    │   └─ Assign session IDs
    │
    └─ Validation
    │
    ▼
Phase 3: LOAD
    │
    ├─ Merge (Incremental mode)
    ├─ Write to Parquet/Iceberg
    └─ Optimize storage
```

## Data Flow

```
Input Data (Parquet/CSV)
    │
    ▼
┌─────────────────────────┐
│  EXTRACT Phase          │
│  @timed_phase("extract")│
│  - File Discovery       │
│  - File Reading         │
│  - Records: 100K-5M     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  TRANSFORM Phase        │
│  @timed_phase(...)      │
│  - Quality Checks       │
│  - Type Casting         │
│  - Null Handling        │
│  - Deduplication        │
│  - Sessionization       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  LOAD Phase             │
│  @timed_phase("load")   │
│  - Merge (if incr.)     │
│  - Write Parquet        │
│  - Or Iceberg Table     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Timing Metrics         │
│  - Phase breakdown      │
│  - Memory usage         │
│  - JSON export          │
└─────────────────────────┘
```

## Component Responsibilities

### Data Generation (`src/data_generation/`)
- Generate realistic clickstream data using Faker
- Configurable sizes: Small (100K), Medium (1M), Large (5M)
- Output to Parquet format
- Includes bulk and incremental data generation

### Polars ETL (`src/etl/polars_etl.py`)
- Single-node optimized processing
- Lazy evaluation with eager execution
- Low overhead, fast startup (~0.05s)
- Efficient memory usage
- Uses `@timed_phase()` decorators for clean timing

### Spark ETL (`src/etl/spark_etl.py`)
- Distributed processing capability
- Adaptive query execution
- Scalable for large datasets
- Higher startup overhead (~3-5s)
- Uses `PipelineTimer` for timing

### Timing Decorator (`src/etl/timing_decorator.py`)
- Clean, non-intrusive timing via decorators
- Tracks Extract, Transform, Load phases
- Monitors memory usage (peak and average)
- Exports metrics to JSON

### Benchmark Orchestration
- `scripts/benchmark_full.py`: Run bulk + incremental for both frameworks
- `scripts/run_comprehensive_benchmark.py`: Run all sizes (small, medium, large)
- `scripts/generate_presentation.py`: Create PowerPoint from results
- `Makefile`: Convenient targets for all operations

## Deployment Options

### Local Development (Current)
```
Developer Machine (WSL2)
    │
    ├─ Python 3.12+ Environment
    ├─ Polars (pip install polars)
    ├─ PySpark (pip install pyspark)
    ├─ Direct execution (no containers)
    └─ Timing decorator for metrics
```

**Why Local?**
- Podman Desktop volume mount issues with WSL
- Eliminates container overhead for accurate timing
- Simpler setup and faster iteration
- Sufficient for benchmarking up to 5M records

### Docker (Available but not used for benchmarks)
```
Docker/Podman Host
    │
    ├─ Polars Container (Dockerfile.pythonic)
    │   └─ Python + Polars + Dependencies
    │
    ├─ Spark Container (Dockerfile.spark)
    │   └─ PySpark + Java + Dependencies
    │
    └─ Note: Volume mount issues with Podman Desktop
        prevent reliable benchmarking
```

### Kubernetes (Future)
```
K8s Cluster
    │
    ├─ Polars Job
    │   └─ Single Pod (no distribution needed)
    │
    ├─ Spark Job
    │   ├─ Driver Pod
    │   └─ Executor Pods (N) for distributed processing
    │
    └─ Storage
        └─ Iceberg tables for data lakehouse
```

## Performance Characteristics

### Polars
- **Strengths**: Low overhead, fast single-node, minimal memory, simple deployment
- **Best For**: < 10M records, single machine, local development
- **Startup**: ~0.05s
- **Memory**: 2-3x lower than Spark
- **Typical Speedup**: 2-3x faster than Spark for single-node workloads

### Spark
- **Strengths**: Distributed processing, scalability, fault tolerance, rich ecosystem
- **Best For**: > 100M records, distributed workloads, existing Spark infrastructure
- **Startup**: ~3-5s (session initialization overhead)
- **Memory**: Higher due to JVM and distributed architecture
- **When Advantageous**: Data > 100GB, multi-node clusters, complex ML workflows

### Benchmark Results (Local Machine)
- **Small (100K)**: Polars ~2x faster
- **Medium (1M)**: Polars ~2x faster
- **Large (5M)**: Polars ~2x faster
- **Pattern**: Spark's startup overhead dominates at these scales

## Technology Stack

### Core
- **Python 3.12+**: Primary language
- **Polars 0.20+**: Single-node DataFrame library with Rust backend
- **PySpark 3.5+**: Distributed processing framework
- **PyArrow**: Columnar data format (used by both)

### Data & Testing
- **Faker**: Realistic test data generation
- **PyIceberg**: Iceberg table format support
- **psutil**: Resource monitoring (CPU, memory)

### Presentation & Analysis
- **python-pptx**: PowerPoint generation
- **JSON**: Metrics export format

### Containerization (Optional)
- **Docker/Podman**: Container runtime
- **Note**: Currently not used for benchmarks due to volume mount issues

### Development
- **Make**: Build automation
- **pytest**: Testing framework
- **ruff**: Linting and formatting

## Metrics Collected

### Timing Metrics (via Decorator)
- **Startup Time**: Framework initialization
- **Extract Phase**: File discovery + reading
- **Transform Phase**:
  - Quality checks (type casting, null handling, deduplication)
  - Sessionization (30-minute inactivity window)
- **Load Phase**: Merge + write operations
- **Total Time**: End-to-end pipeline execution

### Resource Metrics
- **Peak Memory**: Maximum memory usage (MB)
- **Average Memory**: Mean memory usage (MB)
- **CPU Usage**: Peak and average CPU percentage

### Data Metrics
- **Records Read**: Input record count
- **Records Processed**: After quality checks
- **Records Written**: Output record count
- **Records Dropped**: Failed quality checks
- **Records Corrected**: Fixed by quality rules

### Output Formats
- **JSON**: Detailed timing metrics per run
- **Console**: Real-time summary during execution
- **PowerPoint**: Comprehensive analysis and recommendations

## Extension Points

### Adding New ETL Operations
1. Add method to pipeline class (both Polars and Spark)
2. Decorate with `@timed_phase("phase_name", "subphase_name")`
3. Keep logic equivalent across frameworks
4. Test and benchmark

### Adding New Data Sizes
1. Update `SIZE_RECORD_COUNTS` in `generator.py`
2. Generate data: `make generate-data-full SIZE=newsize`
3. Run benchmark: `make benchmark-full SIZE=newsize`
4. Update presentation script to include new size

### Adding New Metrics
1. Extend `PipelineTimer` in `timing_decorator.py`
2. Add new metric fields to `metrics` dictionary
3. Update `log_summary()` to display new metrics
4. Update presentation script to visualize

### Adding New Output Formats
1. Create new export function in timing decorator
2. Add to `run_pipeline()` return value
3. Update benchmark scripts to save new format
4. Document usage

## Key Design Decisions

### Why Decorators for Timing?
- **Clean Code**: No timing logic mixed with business logic
- **Maintainable**: Centralized timing in one module
- **Consistent**: Same approach for both frameworks
- **Non-intrusive**: Easy to add/remove without changing ETL code

### Why Local Benchmarks?
- **Accuracy**: No container overhead skewing results
- **Simplicity**: Easier to run and debug
- **Sufficient**: Single-machine comparison is the goal
- **Practical**: Podman Desktop volume mount issues

### Why These Data Sizes?
- **Small (100K)**: Quick iteration, development testing
- **Medium (1M)**: Realistic single-machine workload
- **Large (5M)**: Stress test without overwhelming local machine
- **Scalable**: Shows performance trends across sizes

### Why Both Bulk and Incremental?
- **Bulk**: Initial historical data load (30 days)
- **Incremental**: Daily updates with merge logic
- **Real-world**: Both patterns common in production
- **Comparison**: Tests different code paths

## Current State

### Implemented ✅
- Clean timing decorator for non-intrusive performance tracking
- Polars and Spark ETL pipelines with sessionization
- Data quality checks and validation
- Bulk and incremental processing modes
- Iceberg table support (optional)
- Comprehensive benchmark orchestration
- JSON metrics export
- PowerPoint presentation generation
- Local execution environment

### Known Limitations ⚠️
- **Podman Desktop**: Volume mount issues prevent containerized benchmarks
- **Data Scale**: Limited to 5M records for local machine
- **Single Node**: No distributed Spark testing
- **No K8s**: Kubernetes deployment not tested

### Not Implemented ❌
- Docker benchmark (volume mount issues)
- Kubernetes deployment
- Distributed Spark cluster testing
- Real-time streaming comparison
- Cost analysis

## Future Enhancements

### Short Term
1. Fix Podman Desktop volume mount issues
2. Add more data quality rules
3. Implement data profiling metrics
4. Add visualization charts to presentation

### Medium Term
1. Kubernetes deployment and benchmarking
2. Distributed Spark cluster comparison
3. Cost analysis (compute time × resource cost)
4. Streaming workload comparison

### Long Term
1. Auto-scaling benchmarks
2. Multi-cloud deployment
3. Real production workload simulation
4. ML pipeline integration
