# Scripts Summary

## Available Benchmark Scripts

### 1. Local Benchmarks (Python)

#### `scripts/benchmark_full.py` (17K)
**Purpose**: Comprehensive local benchmark (bulk + incremental)

**Usage**:
```bash
make benchmark-full SIZE=small
# or
.venv/bin/python scripts/benchmark_full.py --size small
```

**Features**:
- Runs Polars and Spark ETL directly
- Supports Iceberg tables (`--use-iceberg`)
- Detailed JSON output
- Fastest execution

---

### 2. Container Benchmarks (Bash)

#### `scripts/benchmark_docker.sh` (NEW)
**Purpose**: Simple Docker/Podman benchmark

**Usage**:
```bash
make benchmark-docker SIZE=small
# or
./scripts/benchmark_docker.sh
# or
DATA_SIZE=medium ./scripts/benchmark_docker.sh
```

**Features**:
- Auto-detects Docker/Podman
- Builds images automatically
- Runs bulk + incremental for both frameworks
- Simple bash script (no Python dependencies)
- Production-like environment

---

### 3. Kubernetes Benchmarks (Bash)

#### `scripts/k8s_benchmark.sh` (NEW)
**Purpose**: Kubernetes cluster benchmark

**Usage**:
```bash
make k8s-benchmark
# or
./scripts/k8s_benchmark.sh
```

**Features**:
- Runs as Kubernetes Jobs
- Tests distributed execution
- Collects logs from pods
- Measures pod scheduling overhead

---

### 4. Utilities

#### `scripts/verify_iceberg.py` (4.8K)
**Purpose**: Verify Iceberg table setup

**Usage**:
```bash
.venv/bin/python scripts/verify_iceberg.py
```

**Features**:
- Shows table metadata
- Displays sample data
- Statistics and distribution
- Validates Iceberg configuration

---

## Deprecated/Removed Scripts

The following scripts were removed during cleanup:

- ❌ `benchmark.py` → Replaced by `benchmark_docker.sh`
- ❌ `benchmark_incremental.py` → Replaced by `benchmark_full.py`
- ❌ `compare_etl.sh` → Replaced by `benchmark_docker.sh`
- ❌ `detailed_comparison.sh` → Replaced by `benchmark_docker.sh`
- ❌ `k8s_compare_simple.sh` → Replaced by `k8s_benchmark.sh`
- ❌ `kind_k8s_comparison.sh` → Replaced by `k8s_benchmark.sh`
- ❌ `benchmark_containers.py` → Replaced by `benchmark_docker.sh` (simpler)

---

## Quick Reference

### Generate Data (Do This First!)
```bash
make generate-data-full SIZE=small
```

### Run Benchmarks

| Command | Type | Speed | Best For |
|---------|------|-------|----------|
| `make benchmark-full SIZE=small` | Local | ⚡⚡⚡ | Development |
| `make benchmark-docker SIZE=small` | Container | ⚡⚡ | CI/CD |
| `make k8s-benchmark` | Kubernetes | ⚡ | Production |

### View Results
```bash
ls -lh benchmark_results/
cat benchmark_results/*.json | jq .
```

---

## File Structure

```
scripts/
├── benchmark_full.py          # Local benchmark (Python)
├── benchmark_docker.sh         # Docker/Podman benchmark (Bash)
├── k8s_benchmark.sh           # Kubernetes benchmark (Bash)
└── verify_iceberg.py          # Iceberg verification (Python)
```

---

## Design Philosophy

### Simple Bash Scripts
- ✅ No Python dependencies for container/K8s benchmarks
- ✅ Easy to read and modify
- ✅ Works on any system with bash
- ✅ Clear, linear execution flow

### Separation of Concerns
- ✅ Data generation is separate (done once)
- ✅ Benchmarks only measure ETL performance
- ✅ Each script has single responsibility

### Reproducibility
- ✅ Same data for all benchmarks
- ✅ Consistent measurement methodology
- ✅ JSON output for analysis

---

## Summary

**For quick local testing:**
```bash
make benchmark-full SIZE=small
```

**For container testing:**
```bash
make benchmark-docker SIZE=small
```

**For Kubernetes testing:**
```bash
make k8s-benchmark
```

All scripts assume test data already exists in `data/generated/`.
