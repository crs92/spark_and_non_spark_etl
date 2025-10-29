# Benchmark Comparison Guide

## Overview

This project provides **3 different benchmark approaches** to compare Polars and Spark ETL frameworks:

1. **Local Benchmark** - Direct Python execution (fastest, simplest)
2. **Container Benchmark** - Docker/Podman execution (production-like)
3. **Kubernetes Benchmark** - K8s cluster execution (distributed, scalable)

## 1. Local Benchmark (Recommended for Development)

### Description
Runs ETL pipelines directly using Python in your local environment.

### Pros
- ✅ Fastest execution
- ✅ No container overhead
- ✅ Easy to debug
- ✅ Supports Iceberg tables

### Cons
- ❌ Not representative of production deployment
- ❌ Environment-dependent results

### Usage

```bash
# Run complete benchmark (bulk + incremental)
make benchmark-full SIZE=small

# Or directly with Python
.venv/bin/python scripts/benchmark_full.py --size small

# With Iceberg tables
.venv/bin/python scripts/benchmark_full.py --size small --use-iceberg
```

### Output
- Console: Detailed comparison table
- File: `benchmark_results/benchmark_full_small_TIMESTAMP.json`

### Example Results (Small Dataset)
```
BULK PROCESSING (30 days historical data)
Metric                                   Polars               Spark
Total Time (s)                           0.53                 28.92
Records Processed                        99,574               99,574

✓ Winner: POLARS (54.07x faster, 98.2% advantage)

INCREMENTAL PROCESSING (7 days daily files + merge)
Metric                                   Polars               Spark
Total Time (s)                           0.44                 7.62
Records Processed                        106,146              106,234

✓ Winner: POLARS (17.34x faster, 94.2% advantage)
```

## 2. Container Benchmark (Recommended for Production Testing)

### Description
Runs ETL pipelines inside Docker/Podman containers to simulate production deployment.

### Pros
- ✅ Production-like environment
- ✅ Isolated execution
- ✅ Reproducible across machines
- ✅ Includes container startup overhead

### Cons
- ❌ Slower than local (container overhead)
- ❌ Requires Docker/Podman installed
- ❌ Cannot use Iceberg (uses file-based output)

### Usage

```bash
# Run container benchmark (auto-detects Docker/Podman)
make benchmark-containers SIZE=small

# Or directly with Python
.venv/bin/python scripts/benchmark_containers.py --size small

# Specify runtime explicitly
.venv/bin/python scripts/benchmark_containers.py --size small --runtime podman
.venv/bin/python scripts/benchmark_containers.py --size small --runtime docker
```

### What It Does
1. Builds Docker images for both frameworks
2. Runs Polars ETL in container (bulk + incremental)
3. Runs Spark ETL in container (bulk + incremental)
4. Compares total execution time (including container startup)

### Output
- Console: Comparison summary
- File: `benchmark_results/container_benchmark_small_TIMESTAMP.json`

### Example Results
```
CONTAINER BENCHMARK RESULTS
Container Runtime: podman
Data Size: small

BULK PROCESSING:
  Polars: 2.5s
  Spark:  45.3s
  Winner: POLARS (18.12x faster)

INCREMENTAL PROCESSING:
  Polars: 2.1s
  Spark:  38.7s
  Winner: POLARS (18.43x faster)

TOTAL (Bulk + Incremental):
  Polars: 4.6s
  Spark:  84.0s
  Winner: POLARS (18.26x faster)
```

## 3. Kubernetes Benchmark (For Distributed Testing)

### Description
Runs ETL pipelines as Kubernetes Jobs to test distributed execution.

### Pros
- ✅ True distributed environment
- ✅ Scalable (can test with multiple nodes)
- ✅ Production-grade orchestration
- ✅ Tests pod scheduling overhead

### Cons
- ❌ Requires K8s cluster
- ❌ Most complex setup
- ❌ Slowest (includes pod scheduling)
- ❌ Overkill for small datasets

### Prerequisites

1. **Kubernetes cluster** (local or cloud)
   ```bash
   # Local cluster with kind
   kind create cluster --name etl-benchmark

   # Or use minikube
   minikube start

   # Or use existing cluster
   kubectl cluster-info
   ```

2. **Docker images pushed to registry**
   ```bash
   # Build images
   make docker-build

   # Tag for registry
   docker tag pythonic-etl:latest your-registry/pythonic-etl:latest
   docker tag spark-etl:latest your-registry/spark-etl:latest

   # Push to registry
   docker push your-registry/pythonic-etl:latest
   docker push your-registry/spark-etl:latest
   ```

3. **Update K8s manifests** with your registry
   ```bash
   # Edit k8s/pythonic-etl-job.yaml
   # Edit k8s/spark-etl-job.yaml
   # Change image: to your-registry/...
   ```

### Usage

```bash
# Setup K8s infrastructure (first time only)
make k8s-setup

# Run benchmark
make k8s-benchmark

# Or directly
./scripts/k8s_benchmark.sh

# Clean up
make k8s-clean
```

### What It Does
1. Creates Kubernetes Jobs for both frameworks
2. Waits for jobs to complete
3. Collects logs and timing metrics
4. Compares execution times

### Output
- Console: Comparison summary
- Files:
  - `benchmark_results/k8s_benchmark_TIMESTAMP.json`
  - `benchmark_results/pythonic_k8s_TIMESTAMP.log`
  - `benchmark_results/spark_k8s_TIMESTAMP.log`

### Example Results
```
KUBERNETES BENCHMARK RESULTS
Framework            Time (seconds)
--------------------------------------------
Polars (Pythonic)              12
Spark                          67
--------------------------------------------
Winner: Polars (458% faster)
```

## Comparison Matrix

| Feature | Local | Container | Kubernetes |
|---------|-------|-----------|------------|
| **Speed** | ⚡⚡⚡ Fastest | ⚡⚡ Fast | ⚡ Slow |
| **Setup** | ✅ Simple | ✅ Simple | ❌ Complex |
| **Reproducibility** | ⚠️ Environment-dependent | ✅ High | ✅ Very High |
| **Production-like** | ❌ No | ✅ Yes | ✅✅ Very Yes |
| **Iceberg Support** | ✅ Yes | ❌ No | ❌ No |
| **Distributed Testing** | ❌ No | ❌ No | ✅ Yes |
| **Best For** | Development | CI/CD | Production validation |

## Recommendations

### For Development & Iteration
Use **Local Benchmark**:
```bash
make benchmark-full SIZE=small
```
- Fastest feedback loop
- Easy debugging
- Supports Iceberg tables

### For CI/CD Pipelines
Use **Container Benchmark**:
```bash
make benchmark-containers SIZE=small
```
- Reproducible across environments
- Tests containerized deployment
- Reasonable execution time

### For Production Validation
Use **Kubernetes Benchmark**:
```bash
make k8s-benchmark
```
- Tests real deployment scenario
- Validates distributed execution
- Includes orchestration overhead

## Performance Expectations

### Small Dataset (100K records)

| Benchmark Type | Polars | Spark | Winner |
|----------------|--------|-------|--------|
| **Local** | ~1s | ~37s | Polars (37x) |
| **Container** | ~5s | ~84s | Polars (17x) |
| **Kubernetes** | ~12s | ~67s | Polars (5.6x) |

### Key Insights

1. **Polars Advantages**:
   - Minimal startup overhead
   - Fast for single-node workloads
   - Excellent for datasets < 10GB

2. **Spark Advantages**:
   - Better for distributed processing
   - Scales to 100GB+ datasets
   - Production-grade fault tolerance

3. **Container Overhead**:
   - Adds ~4s for Polars
   - Adds ~47s for Spark (JVM startup)

4. **K8s Overhead**:
   - Adds pod scheduling time (~5-10s)
   - Network latency
   - Resource allocation delays

## Troubleshooting

### Container Benchmark Issues

**Error: No container runtime found**
```bash
# Install Docker
sudo apt-get install docker.io

# Or install Podman
sudo apt-get install podman
```

**Error: Permission denied**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Kubernetes Benchmark Issues

**Error: Cannot connect to cluster**
```bash
# Check cluster status
kubectl cluster-info

# Check context
kubectl config current-context

# Switch context if needed
kubectl config use-context your-cluster
```

**Error: Image pull failed**
```bash
# Ensure images are pushed to accessible registry
docker push your-registry/pythonic-etl:latest
docker push your-registry/spark-etl:latest

# Update K8s manifests with correct image names
```

## Summary

Choose your benchmark approach based on your needs:

- 🏃 **Quick comparison?** → Local benchmark
- 🐳 **Testing containers?** → Container benchmark
- ☸️ **Production validation?** → Kubernetes benchmark

All three approaches provide valuable insights into framework performance at different deployment stages.
