# Modern ETL Stack Comparison PoC

A comprehensive Proof of Concept comparing **Spark-based ETL** vs **Python-native ETL** performance across different data sizes and deployment scenarios.

## 🎯 Project Overview

This project evaluates two ETL approaches:
- **Spark Stack**: PySpark + Apache Iceberg + distributed processing
- **Pythonic Stack**: Polars + DuckDB + PyIceberg + single-node optimization

### Key Objectives
- Compare **execution performance** across data sizes (small, medium, large)
- Measure **startup overhead** and **total deployment time**
- Analyze **resource efficiency** (memory, CPU usage)
- Evaluate **scalability characteristics** (vertical vs horizontal scaling)
- Provide **cost-effectiveness analysis** and decision framework

## 🏗️ Architecture

### Two-Image Docker Setup

We use **separate Docker images** to ensure fair comparison and measure complete deployment overhead:

#### 1. Spark ETL Image (`Dockerfile.spark`)
```dockerfile
FROM bitnami/spark:3.5
# Optimized for distributed processing
# Includes: PySpark, PyArrow, PyIceberg
# Java/Spark initialization overhead
```

#### 2. Pythonic ETL Image (`Dockerfile.pythonic`)
```dockerfile
FROM python:3.11-slim
# Optimized for single-node performance
# Includes: Polars, DuckDB, PyIceberg
# Minimal startup overhead
```

### Infrastructure Services
- **MinIO**: S3-compatible storage for Iceberg data lakehouse
- **PostgreSQL**: Iceberg catalog metadata store
- **Spark Cluster**: Master/worker nodes for distributed testing

## 🚀 Quick Start

### Docker Commands

```bash
# Build both ETL images
make docker-build

# Build individual images
make docker-build-spark      # Spark-based ETL
make docker-build-pythonic   # Python-native ETL

# Start infrastructure
make docker-up

# Run ETL pipelines individually
make docker-run-spark        # Test Spark approach
make docker-run-pythonic     # Test Pythonic approach

# Run comprehensive benchmark
make docker-benchmark        # Compare both approaches
```

### Kubernetes Deployment
```bash
# Kubernetes benchmarking
chmod +x scripts/k8s_benchmark.sh
./scripts/k8s_benchmark.sh
```

## 📊 Benchmarking Framework

### Automated Performance Measurement

The `scripts/benchmark.py` measures:

| Metric | Description | Requirement |
|--------|-------------|-------------|
| **Image Pull Time** | Time to download and extract image | NF.1.2 (Startup) |
| **Container Start** | Time to initialize container | NF.1.2 (Startup) |
| **Execution Time** | Pure ETL processing time | NF.1.1 (Performance) |
| **Total Time** | End-to-end pipeline time | Combined metric |
| **Peak Memory** | Maximum RAM utilization | NF.2.1 (Resources) |
| **CPU Usage** | Average CPU consumption | NF.2.2 (Resources) |

### Sample Benchmark Output
```
ETL STACK COMPARISON RESULTS
============================================================
Metric                    Pythonic        Spark           Winner
-------------------------------------------------------------
Image Pull Time (s)       45.20          127.50          Pythonic
Container Start (s)       2.10           8.30            Pythonic
Execution Time (s)         12.45          18.20           Pythonic
Total Time (s)             59.75          154.00          Pythonic
Peak Memory (MB)           512.30         1024.80         Pythonic
Avg CPU (%)               78.50          65.20           Spark
============================================================
```

## 🔧 Development Environment

### Project Setup & Best Practices

This project uses [uv](https://github.com/astral-sh/uv) for Python package management, [pre-commit](https://pre-commit.com/) for git hooks, [ruff](https://docs.astral.sh/ruff/) for linting, and [black](https://black.readthedocs.io/en/stable/) for code formatting.

### 1. Create and activate the virtual environment
```bash
uv venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
uv pip install -r requirements.txt  # if you have requirements.txt
uv pip install pre-commit ruff black
```

### 3. Pre-commit setup
```bash
pre-commit install
```
This will enable automatic code checks (ruff, black) before each commit.

### 4. Manual checks
- Run ruff: `ruff .`
- Run black: `black .`

### 5. Configuration
- All tool configurations are in `pyproject.toml`.
- Pre-commit hooks are in `.pre-commit-config.yaml`.

## 📁 Project Structure

```
spark_and_non_spark_etl/
├── src/
│   ├── etl/
│   │   ├── spark_etl.py          # Spark-based ETL implementation
│   │   └── non_spark_etl.py      # Pythonic ETL implementation
│   └── utils/
│       └── helpers.py            # Shared utilities
├── tests/
│   ├── test_spark_etl.py         # Spark ETL tests
│   └── test_non_spark_etl.py     # Pythonic ETL tests
├── scripts/
│   ├── benchmark.py              # Performance benchmarking
│   └── k8s_benchmark.sh          # Kubernetes benchmarking
├── k8s/
│   ├── spark-etl-job.yaml        # Spark Kubernetes job
│   └── pythonic-etl-job.yaml     # Pythonic Kubernetes job
├── docker/
│   └── init-postgres.sql         # Database initialization
├── data/
│   ├── input/                    # Test datasets
│   └── output/                   # ETL results
├── notebooks/                    # Jupyter notebooks for analysis
├── Dockerfile.spark              # Spark ETL image
├── Dockerfile.pythonic           # Pythonic ETL image
├── docker-compose.yml            # Multi-service orchestration
├── Makefile                      # Automation commands
├── pyproject.toml               # Dependencies and configuration
├── requirements.md              # Functional requirements
└── dod.md                       # Definition of Done checklist
```

## 🎯 ETL Pipeline Features

### Data Processing Pipeline (F.1, F.2, F.3)
1. **Data Ingestion**: CSV/Parquet file processing
2. **Data Cleansing**: Null handling and type casting
3. **IP Geolocation**: Country derivation from IP addresses
4. **Sessionization**: 30-minute inactivity window grouping
5. **Data Loading**: Apache Iceberg lakehouse storage

### Analytics & Querying (F.5)
- **DuckDB**: High-performance analytical queries
- **SQL Interface**: Standard SQL queries against processed data
- **Performance Validation**: Query performance comparison

## 🧪 Testing Strategy

### Test Data Sizes
- **Small** (< 1GB): Development and rapid iteration
- **Medium** (1-10GB): Performance baseline testing
- **Large** (> 10GB): Scalability evaluation

### Scaling Approaches
- **Vertical Scaling** (NF.3.1): Single large, memory-optimized machine
- **Horizontal Scaling** (NF.3.2): Distributed cluster of smaller machines

## 📈 Decision Framework

The PoC generates a **decision framework** with heuristics for choosing ETL architecture based on:

- **Data Volume**: Size of datasets to process
- **Processing Frequency**: Batch vs real-time requirements
- **Infrastructure Constraints**: Available resources and budget
- **Team Expertise**: Spark vs Python-native skillsets
- **Performance Requirements**: Latency and throughput needs

## 🔍 Monitoring & Observability

### Metrics Collection
- **Docker Stats**: Container resource usage
- **Process Monitoring**: CPU and memory profiling
- **Execution Logs**: Detailed pipeline execution logs
- **Performance Profiles**: Memory and CPU profiling data

### Results Output
- **JSON Reports**: Structured benchmark results
- **Comparison Tables**: Side-by-side performance metrics
- **Resource Graphs**: CPU and memory usage over time
- **Cost Analysis**: Infrastructure cost projections

## 🚢 Deployment Options

### Local Development
```bash
# Single-node benchmark (Docker)
make docker-up              # Start infrastructure
make docker-run-pythonic    # Run Pythonic ETL
make docker-run-spark       # Run Spark ETL
make docker-benchmark       # Compare both approaches
```

### Distributed Testing
```bash
# Kubernetes distributed benchmark
make k8s-setup              # Setup K8s cluster
make k8s-benchmark          # Run distributed comparison
```

### Kubernetes Production
```bash
kubectl apply -f k8s/       # Deploy ETL jobs
./scripts/k8s_benchmark.sh  # Run K8s benchmarks
```

### Service Access Points
- **Jupyter Lab**: http://localhost:8889 (interactive development)
- **MinIO Console**: http://localhost:9001 (data storage admin)
- **Spark UI**: http://localhost:8080 (Spark cluster monitoring)
- **PostgreSQL**: localhost:5432 (catalog database)

## 📋 Requirements Traceability

| Requirement | Implementation | Validation |
|-------------|----------------|------------|
| **F.1** - Data Ingestion | CSV/Parquet readers in both ETL stacks | Unit tests |
| **F.2** - Data Transformation | Identical business logic implementation | Integration tests |
| **F.3** - Data Loading | Apache Iceberg integration | End-to-end tests |
| **F.4** - Pipeline Equivalence | Shared test datasets and validation | Diff comparison |
| **F.5** - Analytical Queries | DuckDB SQL interface | Query tests |
| **NF.1** - Performance | Automated benchmarking framework | Continuous measurement |
| **NF.2** - Resource Efficiency | Docker stats and profiling | Resource monitoring |
| **NF.3** - Scalability | Multi-node and single-node testing | Scaling tests |
| **NF.4** - Cost-Effectiveness | Cost analysis in benchmark reports | Economic modeling |

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** changes (`git commit -m 'Add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Quality
- All code must pass `ruff` linting
- Code must be formatted with `black`
- Tests must pass before merging
- Pre-commit hooks enforce quality standards

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Apache Spark** team for the distributed processing framework
- **Polars** team for high-performance DataFrame operations
- **DuckDB** team for analytical query engine
- **Apache Iceberg** team for data lakehouse table format
