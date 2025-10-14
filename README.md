# Spark vs Polars ETL Benchmark

A simple, incremental ETL pipeline comparison between **Apache Spark** and **Polars**.

## What This Does

Compares Spark and Polars performance across 5 incremental ETL steps:

1. **Read** - Load CSV data
2. **Transform** - Type casting and data cleaning
3. **Load** - Write to storage (Parquet)
4. **Merge** - Join with other datasets
5. **Additional** - Aggregations and enrichment

Each step is timed independently for detailed performance analysis.

## Quick Start

### 1. Install Dependencies

```bash
make install
```

This uses `uv` to install all dependencies from `pyproject.toml`.

### 2. Generate Test Data

```bash
python -m src.data_generation.generator \
  --num-records 10000 \
  --output data/generated/test_data.csv
```

### 3. Run Benchmark

```bash
# Run all 5 steps
python scripts/benchmark_incremental.py \
  --input data/generated/test_data.csv

# Run only first 3 steps
python scripts/benchmark_incremental.py \
  --input data/generated/test_data.csv \
  --steps 3
```

### 4. View Results

Results are printed to console and saved to `data/benchmarks/benchmark_results_*.json`

## Example Output

```
================================================================================
COMPARISON RESULTS
================================================================================

Metric                         Polars          Spark           Winner
----------------------------------------------------------------------
Total Time (s)                 0.15            9.23            Polars
Step 1 Read                    0.08            5.12            Polars
Step 2 Transform               0.04            2.45            Polars
Step 3 Load                    0.03            1.66            Polars
Records Processed              10,000          10,000

✓ Polars is 98.4% faster
================================================================================
```

## Project Structure

```
spark_and_non_spark_etl/
├── src/
│   ├── data_generation/
│   │   └── generator.py          # Generate test data with Faker
│   │
│   └── etl/
│       ├── polars_etl.py          # Polars incremental pipeline
│       ├── spark_etl_incremental.py  # Spark incremental pipeline
│       └── data_quality.py        # Shared utilities
│
├── scripts/
│   └── benchmark_incremental.py   # Benchmark script (local + K8s)
│
├── tests/                         # Test suite
├── k8s/                           # Kubernetes manifests
├── docker/                        # Docker configuration
│
├── Dockerfile.spark               # Spark Docker image
├── Dockerfile.pythonic            # Polars Docker image
├── docker-compose.yml             # Local orchestration
│
├── README.md                      # This file
└── ARCHITECTURE.md                # Architecture diagram
```

## Running Individual ETL Pipelines

### Polars ETL

```bash
# Run all steps
python -m src.etl.polars_etl

# Run only first 3 steps
python -m src.etl.polars_etl 3
```

### Spark ETL

```bash
# Run all steps
python -m src.etl.spark_etl_incremental

# Run only first 3 steps
python -m src.etl.spark_etl_incremental 3
```

## Docker Deployment

### Build Images

```bash
make docker-build
```

### Run with Docker

```bash
# Start infrastructure
make docker-up

# Run Polars ETL
make docker-run-pythonic

# Run Spark ETL
make docker-run-spark

# Run benchmark
make docker-benchmark
```

## Kubernetes Deployment

### Setup Kubernetes

```bash
make k8s-setup
```

### Run Benchmark

```bash
make k8s-benchmark
```

### View Logs

```bash
kubectl logs -l job-name=pythonic-etl-job
kubectl logs -l job-name=spark-etl-job
```

### Cleanup

```bash
make k8s-clean
```

## Incremental Development

The ETL pipelines are designed to be extended incrementally:

### Adding a New Step

1. **Add method to pipeline class**:
```python
def step_6_custom(self):
    """Step 6: Your custom logic."""
    logger.info("Step 6: Custom processing")
    start = time.time()

    # Your logic here

    self.metrics['step_6_custom'] = time.time() - start
    return self.df
```

2. **Update run_pipeline method**:
```python
if steps >= 6:
    self.step_6_custom()
```

3. **Run benchmark**:
```bash
python scripts/benchmark_incremental.py --input data.csv --steps 6
```

## Testing

```bash
# Run all tests
make test

# Run code quality checks
make check

# Format code
make format

# Run everything (checks + tests)
make all
```

## Performance Insights

### Small Datasets (< 100K records)
- **Polars**: 95-99% faster
- **Reason**: Lower startup overhead, optimized single-node execution
- **Recommendation**: Use Polars

### Medium Datasets (100K - 10M records)
- **Mixed Results**: Depends on complexity
- **Recommendation**: Benchmark your specific workload

### Large Datasets (> 10M records)
- **Spark**: Better scalability with distributed processing
- **Recommendation**: Use Spark for distributed workloads

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture diagrams and data flow.

## Common Commands

```bash
# Setup
make install                    # Install dependencies with uv
make help                       # Show all available commands

# Development
make test                       # Run tests
make check                      # Run code quality checks
make format                     # Format code
make clean                      # Clean temporary files

# Data & Benchmarks
python -m src.data_generation.generator --num-records 10000
python scripts/benchmark_incremental.py --input data/generated/test_data.csv

# Run individual ETL
python -m src.etl.polars_etl
python -m src.etl.spark_etl_incremental

# Docker
make docker-build               # Build images
make docker-up                  # Start infrastructure
make docker-run-pythonic        # Run Polars ETL
make docker-run-spark           # Run Spark ETL
make docker-benchmark           # Run benchmark
make docker-down                # Stop services

# Kubernetes
make k8s-setup                  # Setup K8s cluster
make k8s-benchmark              # Run distributed benchmark
make k8s-clean                  # Cleanup K8s resources
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
