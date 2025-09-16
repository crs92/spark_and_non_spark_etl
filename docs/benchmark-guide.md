# ETL Benchmark Guide

This guide walks you through running performance benchmarks to compare Spark-based vs Pythonic ETL approaches.

## 🎯 Overview

The benchmark measures both **single-node** and **distributed** processing scenarios:

### Single-Node Comparison (Docker)
- **Setup Time**: Image build + container startup time (NF.1.2)
- **Execution Time**: Pure ETL processing time (NF.1.1)
- **Resource Usage**: Memory and CPU consumption (NF.2.1, NF.2.2)
- **Total Time**: End-to-end pipeline completion
- **Expected Winner**: Pythonic ETL (lower overhead for small data)

### Distributed Comparison (Kubernetes)
- **Cluster Setup Time**: Pod scheduling + distributed initialization
- **Distributed Execution**: Multi-node parallel processing
- **Scalability**: Processing larger datasets across multiple nodes
- **Resource Efficiency**: Distributed resource utilization
- **Expected Winner**: Spark ETL (designed for distributed processing)

## 🚀 Benchmark Scenarios

### Scenario 1: Single-Node Performance (Docker)

This tests **startup speed** and **small data processing** where Pythonic ETL should excel:

```bash
# Build both ETL images
make docker-build

# Quick test (no infrastructure)
make docker-test-quick

# Full benchmark with infrastructure
make docker-up
sleep 30
make docker-benchmark
```

### Scenario 2: Distributed Performance (Kubernetes)

This tests **distributed processing** where Spark should show its strength:

```bash
# Setup Kubernetes cluster (minikube, kind, or cloud)
kubectl cluster-info

# Setup RBAC for Spark
kubectl apply -f k8s/spark-rbac.yaml

# Run distributed benchmark
chmod +x scripts/k8s_benchmark.sh
./scripts/k8s_benchmark.sh
```

## 📊 Expected Results Comparison

### Single-Node Results (Docker)
```
ETL STACK COMPARISON RESULTS
============================================================
Metric                    Pythonic        Spark           Winner
-------------------------------------------------------------
Image Pull Time (s)       25.30          145.20          Pythonic
Container Start (s)       1.50           6.80            Pythonic
Execution Time (s)         8.20          12.40           Pythonic
Total Time (s)             35.00          164.40          Pythonic
Peak Memory (MB)           256.50         1024.30         Pythonic
Avg CPU (%)               65.20          45.30           Spark
============================================================
```

### Distributed Results (Kubernetes)
```
KUBERNETES ETL COMPARISON RESULTS
============================================================
Metric                    Pythonic        Spark           Winner
-------------------------------------------------------------
Cluster Setup (s)         15.20          25.40           Pythonic
Distributed Exec (s)      45.30          28.60           Spark
Total Processing (s)      60.50          54.00           Spark
Throughput (GB/min)       1.2            2.8             Spark
Resource Efficiency       Medium         High            Spark
============================================================
```

### What This Means

**Single-Node (Docker) - Pythonic ETL Wins:**
- ✅ **Faster startup** (1.5s vs 6.8s container start)
- ✅ **Smaller image** (25s vs 145s pull time)
- ✅ **Lower memory** (256MB vs 1GB peak usage)
- ✅ **Faster for small data** (8.2s vs 12.4s execution)

**Distributed (Kubernetes) - Spark ETL Wins:**
- ✅ **Better throughput** (2.8 GB/min vs 1.2 GB/min)
- ✅ **Parallel processing** across multiple nodes
- ✅ **Resource efficiency** in distributed scenarios
- ✅ **Scales linearly** with data size

## 🎯 Decision Framework

| Data Size | Infrastructure | Processing Pattern | Recommended Stack |
|-----------|----------------|-------------------|-------------------|
| < 1GB | Single machine | Batch jobs | **Pythonic ETL** |
| 1-10GB | Single machine | Regular ETL | **Pythonic ETL** |
| 10-100GB | Multi-node cluster | Distributed batch | **Spark ETL** |
| > 100GB | Large cluster | Big data processing | **Spark ETL** |
| Any size | Serverless/Functions | Event-driven | **Pythonic ETL** |
| Any size | Existing Spark cluster | Integration | **Spark ETL** |

## 🔧 Manual Testing

### Individual Pipeline Testing

#### Test Pythonic ETL
```bash
# Build image
docker build -f Dockerfile.pythonic -t pythonic-etl .

# Run with mounted data directory
docker run --rm -v $(pwd)/data:/app/data pythonic-etl

# Check output
ls -la data/output/
```

#### Test Spark ETL
```bash
# Build image
docker build -f Dockerfile.spark -t spark-etl .

# Run with mounted data directory
docker run --rm -v $(pwd)/data:/app/data spark-etl

# Check output
ls -la data/output/
```

### Custom Data Testing
```bash
# Place your test files in data/input/
cp your_clickstream_data.csv data/input/

# Run benchmark with your data
make docker-benchmark
```

## 📈 Different Data Sizes

### Small Dataset (< 1GB)
```bash
python scripts/benchmark.py --data-size small
```

### Medium Dataset (1-10GB)
```bash
python scripts/benchmark.py --data-size medium
```

### Large Dataset (> 10GB)
```bash
python scripts/benchmark.py --data-size large
```

## 🐛 Troubleshooting

### Common Issues

#### Docker Build Fails
```bash
# Clean Docker cache
docker system prune -f

# Rebuild images
make docker-build
```

#### Services Won't Start
```bash
# Check service status
docker-compose ps

# View service logs
make docker-logs

# Restart services
make docker-down
make docker-up
```

#### Out of Memory
```bash
# Check Docker resources
docker stats

# Increase Docker memory limit (Docker Desktop)
# Or use smaller test dataset
python scripts/benchmark.py --data-size small
```

#### Permission Errors
```bash
# Fix data directory permissions
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

## 📋 Benchmark Output Files

The benchmark creates several output files:

```
benchmark_results_small_20250916_143022.json  # Main results
benchmark_small_20250916_143022.log           # Execution log
data/output/processed_data.parquet            # Pythonic output
data/output/spark_output/                     # Spark output
```

### Results JSON Structure
```json
{
  "pythonic": {
    "stack_type": "pythonic",
    "image_pull_time": 25.3,
    "container_start_time": 1.5,
    "execution_time": 8.2,
    "total_time": 35.0,
    "peak_memory_mb": 256.5,
    "avg_cpu_percent": 65.2,
    "exit_code": 0,
    "timestamp": "2025-09-16T14:30:22"
  },
  "spark": {
    // Similar structure for Spark results
  }
}
```

## 🎯 Interpreting Results

### When to Choose Pythonic ETL
- **Small to medium datasets** (< 10GB)
- **Fast startup requirements** (batch jobs, serverless)
- **Limited infrastructure** (single machine deployments)
- **Development speed** priority
- **Cost optimization** for small workloads

### When to Choose Spark ETL
- **Large datasets** (> 10GB)
- **Distributed processing** requirements
- **Complex transformations** with SQL
- **Existing Spark infrastructure**
- **Long-running batch jobs** where startup overhead is amortized

## 🧹 Cleanup

### Stop All Services
```bash
make docker-down
```

### Remove All Docker Resources
```bash
make docker-clean
```

### Clean Project Files
```bash
# Remove output files
rm -rf data/output/*
rm -f benchmark_*.json benchmark_*.log

# Remove Docker images
docker rmi pythonic-etl spark-etl
```

## 📝 Next Steps

1. **Analyze Results**: Compare metrics for your specific use case
2. **Test with Real Data**: Use your actual clickstream datasets
3. **Scale Testing**: Try different data sizes and machine configurations
4. **Cost Analysis**: Calculate infrastructure costs for each approach
5. **Decision Documentation**: Update your decision framework with findings

## 🔗 Related Documentation

- [Project README](../README.md) - Overall project overview
- [Requirements](../requirements.md) - Functional and non-functional requirements
- [Definition of Done](../dod.md) - Project checklist and progress tracking
- [Docker Compose](../docker-compose.yml) - Service configuration
