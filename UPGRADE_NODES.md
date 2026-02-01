# EKS Node Upgrade Guide

## Problem
Current nodes (`m6i.large` - 2 vCPU, 8GB) don't have enough capacity for fair Spark vs Polars comparison.

## Solution
Upgrade to `m6i.xlarge` (4 vCPU, 16GB) nodes.

## Steps to Upgrade

### 1. Apply Terraform Changes
```bash
cd terraform
terraform plan
terraform apply
```

This will:
- Create new `m6i.xlarge` node group
- Drain and terminate old `m6i.large` nodes
- Takes ~5-10 minutes

### 2. Verify New Nodes
```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,INSTANCE_TYPE:.metadata.labels.node\\.kubernetes\\.io/instance-type,CPU:.status.capacity.cpu,MEMORY:.status.capacity.memory
```

Expected output:
```
NAME                                           INSTANCE_TYPE   CPU   MEMORY
ip-10-0-x-x.eu-central-1.compute.internal     m6i.xlarge      4     15944736Ki
ip-10-0-x-x.eu-central-1.compute.internal     m6i.xlarge      4     15944736Ki
```

### 3. Check Allocatable Resources
```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,ALLOCATABLE_CPU:.status.allocatable.cpu,ALLOCATABLE_MEMORY:.status.allocatable.memory
```

Expected:
- Allocatable CPU per node: ~3.92 cores (3920m)
- Total across 2 nodes: ~7.84 cores
- Enough for: 1 driver (1 core) + 4 executors (4 cores) = 5 cores ✅

### 4. Delete Stuck Spark Job (if any)
```bash
kubectl delete sparkapplication --all -n default
```

### 5. Rerun Benchmark
```bash
uv run python scripts/run_orchestrated_benchmark.py \
    --spark-jobs 1 \
    --batch-jobs 1 \
    --scale-factor 1 \
    --max-wait-time 600 \
    --output quick_test.json
```

## Resource Comparison After Upgrade

### Scale Factor 1 or 10:
| Platform | Component | vCPU | Memory | Count | **Total vCPU** | **Total Memory** |
|----------|-----------|------|--------|-------|----------------|------------------|
| **EKS (Spark)** | Driver | 1 | 4 GB | 1 | 1 | 4 GB |
| | Executor | 1 | 4 GB | 4 | 4 | 16 GB |
| | **TOTAL** | | | | **5 vCPU** | **20 GB** |
| **AWS Batch (Polars)** | Container | 4 | 16 GB | 1 | **4 vCPU** | **16 GB** |

**Result**: Spark has 25% more vCPU and 25% more memory, but also has distribution overhead. This is a **fair comparison**!

## Cost Impact

### Before (m6i.large):
- $0.096/hour × 2 nodes = **$0.192/hour**
- ~$138/month (24/7)

### After (m6i.xlarge):
- $0.192/hour × 2 nodes = **$0.384/hour**
- ~$276/month (24/7)

**Increase**: $0.192/hour (~$138/month)

For benchmarking, you can scale down when not in use:
```bash
# Scale down to 0 nodes when not benchmarking
kubectl scale deployment --all --replicas=0 -n default
# Or use Terraform to set desired_size = 0
```

## Rollback (if needed)
```bash
cd terraform
git checkout terraform.tfvars  # Revert to m6i.large
terraform apply
```
