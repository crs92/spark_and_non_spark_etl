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
pip install -e .
```

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
docker-compose build
```

### Run with Docker

```bash
# Start infrastructure
docker-compose up -d minio postgres

# Run Polars ETL
docker-compose run pythonic-etl python -m src.etl.polars_etl

# Run Spark ETL
docker-compose run spark-etl python -m src.etl.spark_etl_incremental
```

## Kubernetes Deployment

### Deploy Infrastructure

```bash
kubectl apply -f k8s/infrastructure/
```

### Run ETL Jobs

```bash
# Polars job
kubectl apply -f k8s/pythonic-etl-job.yaml

# Spark job
kubectl apply -f k8s/spark-etl-job.yaml
```

### View Logs

```bash
kubectl logs -l job-name=pythonic-etl-job
kubectl logs -l job-name=spark-etl-job
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
pytest tests/ -v

# Run specific tests
pytest tests/test_polars_etl.py -v
pytest tests/test_spark_etl.py -v
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
# Generate data
python -m src.data_generation.generator --num-records 10000

# Run benchmark
python scripts/benchmark_incremental.py --input data/generated/test_data.csv

# Run individual ETL
python -m src.etl.polars_etl
python -m src.etl.spark_etl_incremental

# Run tests
pytest tests/ -v

# Docker
docker-compose build
docker-compose up -d

# Kubernetes
kubectl apply -f k8s/
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
