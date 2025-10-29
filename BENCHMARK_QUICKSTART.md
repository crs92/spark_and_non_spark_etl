# Benchmark Quick Start Guide

## Simple 3-Step Process

### Step 1: Generate Test Data (Once)

```bash
# Generate small dataset (100K records)
make generate-data-full SIZE=small

# Or medium dataset (10M records)
make generate-data-full SIZE=medium

# Or large dataset (100M records)
make generate-data-full SIZE=large
```

**Note**: You only need to do this once. The data will be reused for all benchmarks.

### Step 2: Choose Your Benchmark

#### Option A: Local Benchmark (Fastest)
```bash
make benchmark-full SIZE=small
```
- Runs directly on your machine
- No containers needed
- ~1 minute for small dataset

#### Option B: Docker/Podman Benchmark (Production-like)
```bash
make benchmark-docker SIZE=small
```
- Runs in containers
- Tests containerized deployment
- ~2-3 minutes for small dataset

#### Option C: Kubernetes Benchmark (Distributed)
```bash
# First time only: setup K8s infrastructure
make k8s-setup

# Run benchmark
make k8s-benchmark
```
- Runs on Kubernetes cluster
- Tests distributed execution
- ~5-10 minutes for small dataset

### Step 3: View Results

Results are saved in `benchmark_results/`:
```bash
# List all results
ls -lh benchmark_results/

# View latest result
cat benchmark_results/*.json | tail -1 | jq .
```

## Complete Examples

### Example 1: Quick Local Test
```bash
# Generate data
make generate-data-full SIZE=small

# Run benchmark
make benchmark-full SIZE=small

# Done! Results in benchmark_results/
```

### Example 2: Docker/Podman Test
```bash
# Generate data (if not already done)
make generate-data-full SIZE=small

# Run Docker benchmark
make benchmark-docker SIZE=small

# Or run the script directly
./scripts/benchmark_docker.sh

# Or with custom size
DATA_SIZE=medium ./scripts/benchmark_docker.sh
```

### Example 3: Kubernetes Test
```bash
# Generate data (if not already done)
make generate-data-full SIZE=small

# Setup K8s (first time only)
make k8s-setup

# Run K8s benchmark
make k8s-benchmark

# Or run the script directly
./scripts/k8s_benchmark.sh

# Clean up K8s resources
make k8s-clean
```

## All Available Commands

```bash
# Data Generation
make generate-data-full SIZE=small    # Generate test data

# Benchmarks
make benchmark-full SIZE=small        # Local benchmark
make benchmark-docker SIZE=small      # Docker/Podman benchmark
make k8s-benchmark                    # Kubernetes benchmark

# Utilities
make docker-build                     # Build Docker images
make k8s-setup                        # Setup K8s infrastructure
make k8s-clean                        # Clean K8s resources
```

## Expected Results (Small Dataset)

| Benchmark Type | Polars | Spark | Winner |
|----------------|--------|-------|--------|
| **Local** | ~1s | ~37s | Polars (37x faster) |
| **Docker** | ~5s | ~84s | Polars (17x faster) |
| **Kubernetes** | ~12s | ~67s | Polars (5.6x faster) |

## Troubleshooting

### "Test data not found"
```bash
# Generate data first
make generate-data-full SIZE=small
```

### "No container runtime found"
```bash
# Install Docker
sudo apt-get install docker.io

# Or install Podman
sudo apt-get install podman
```

### "Cannot connect to Kubernetes cluster"
```bash
# Check if cluster is running
kubectl cluster-info

# Or start local cluster
kind create cluster --name etl-benchmark
```

## What Gets Measured?

All benchmarks measure:
- ✅ **Bulk processing**: Initial load of 30 days historical data
- ✅ **Incremental processing**: Daily incremental files + merge
- ✅ **Total time**: Bulk + Incremental combined

What is **NOT** measured:
- ❌ Data generation time (done separately)
- ❌ Image build time (done once)
- ❌ Infrastructure setup time (done once)

This ensures fair, reproducible comparisons focused purely on ETL performance.

## Summary

**Simplest workflow:**
```bash
# 1. Generate data (once)
make generate-data-full SIZE=small

# 2. Run benchmark (as many times as you want)
make benchmark-full SIZE=small
# or
make benchmark-docker SIZE=small
# or
make k8s-benchmark

# 3. Check results
ls benchmark_results/
```

That's it! 🎉
