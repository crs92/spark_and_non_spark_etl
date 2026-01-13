# Polars + DuckDB ETL on AWS Batch - Complete Guide

## Overview

This guide covers the Polars + DuckDB ETL implementation for TPC-H benchmarking on AWS Batch. This implementation demonstrates modern single-node high-performance data processing as an alternative to distributed systems like Spark.

## Architecture

### Components

1. **Polars + DuckDB ETL** (`src/etl/polars_etl_tpch.py`)
   - DuckDB for S3 access and query execution with pushdown optimizations
   - Polars for data processing with streaming capabilities
   - Comprehensive performance tracking

2. **AWS Batch Infrastructure** (`terraform/batch.tf`)
   - Fargate-based serverless compute
   - Integrated with existing VPC, S3, and ECR
   - IAM roles with S3 access
   - CloudWatch Logs integration

3. **Container** (`Dockerfile.polars-tpch`)
   - Python 3.12 with Polars, DuckDB, PyArrow, boto3
   - Optimized for Fargate deployment

4. **Helper Script** (`scripts/batch_helper.sh`)
   - Simplified job submission and monitoring
   - Automatic Terraform output retrieval

### Key Optimizations

1. **Predicate Pushdown**: Filters applied at Parquet row group level (30-70% I/O reduction)
2. **Projection Pushdown**: Only required columns read from S3 (~81% I/O reduction for 3/16 columns)
3. **Zero-Copy Handoff**: DuckDB → Polars via Apache Arrow (no serialization)
4. **Streaming Mode**: Process datasets larger than RAM with constant memory usage

## Quick Start

### 1. Build and Push Container

```bash
# Build container
docker build -f Dockerfile.polars-tpch -t polars-tpch-etl:latest .

# Get ECR URL and push
cd terraform
ECR_URL=$(terraform output -json ecr_repository_urls | jq -r '.["polars-etl"]')
docker tag polars-tpch-etl:latest ${ECR_URL}:latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ECR_URL}
docker push ${ECR_URL}:latest
```

### 2. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform apply

# Verify outputs
terraform output batch_job_queue_name
terraform output batch_cloudwatch_log_group
```

### 3. Submit and Monitor Job

```bash
# Using helper script (recommended)
./scripts/batch_helper.sh info          # Show resources
./scripts/batch_helper.sh submit 10     # Submit SF 10 job
./scripts/batch_helper.sh list          # List jobs
./scripts/batch_helper.sh logs <JOB_ID> follow  # Tail logs

# Or manually
JOB_QUEUE=$(cd terraform && terraform output -raw batch_job_queue_name)
JOB_DEFINITION=$(cd terraform && terraform output -raw batch_job_definition_arn)
S3_BUCKET=$(cd terraform && terraform output -raw s3_bucket_name)

aws batch submit-job \
  --job-name polars-tpch-sf10-$(date +%s) \
  --job-queue ${JOB_QUEUE} \
  --job-definition ${JOB_DEFINITION} \
  --container-overrides "{
    \"command\": [
      \"--scale-factor\", \"10\",
      \"--s3-input\", \"s3://${S3_BUCKET}/tpch-sf10/\",
      \"--s3-output\", \"s3://${S3_BUCKET}/results/\"
    ]
  }"
```

## Helper Script Commands

```bash
./scripts/batch_helper.sh info              # Show Batch resources
./scripts/batch_helper.sh submit [SF]       # Submit job (default SF 10)
./scripts/batch_helper.sh list [STATUS]     # List jobs (default RUNNING)
./scripts/batch_helper.sh status <JOB_ID>   # Show job status
./scripts/batch_helper.sh logs <JOB_ID> [follow]  # Show logs
./scripts/batch_helper.sh cancel <JOB_ID>   # Cancel job
./scripts/batch_helper.sh help              # Show help
```

## Configuration

### Resource Requirements

Default configuration (adjustable in `terraform/batch.tf`):
- **vCPU**: 4
- **Memory**: 16 GB
- **Timeout**: 3600 seconds (1 hour)
- **Retries**: 2 attempts

### Fargate vCPU/Memory Options

| vCPU | Memory (GB) | Use Case |
|------|-------------|----------|
| 4    | 8-30        | SF 10-50 |
| 8    | 16-60       | SF 50-100 |
| 16   | 32-120      | SF 100+ |

### Environment Variables

Set in job definition:
- `AWS_REGION`: AWS region (default: us-east-1)
- `PYTHONUNBUFFERED`: Enable unbuffered output (set to "1")

## Performance

### Expected Performance (SF 10, ~10GB)

- **Startup**: 2-5 seconds
- **Execution**: 10-20 seconds
- **Memory**: 1-2 GB
- **Cost**: ~$0.02 per run (4 vCPU, 16 GB, 5 minutes)

### Comparison with Spark

| Metric | Polars + DuckDB | PySpark on EKS |
|--------|-----------------|----------------|
| Startup | 2-5s | 30-60s |
| Execution | 10-20s | 30-60s |
| Memory | 1-2 GB | 8-16 GB |
| Cost | $0.02 | $0.10 |
| Complexity | Low | High |

## Troubleshooting

### Log Group Not Found

**Error**: `ResourceNotFoundException: The specified log group does not exist`

**Solution**: Get log group name from Terraform:
```bash
LOG_GROUP=$(cd terraform && terraform output -raw batch_cloudwatch_log_group)
aws logs tail ${LOG_GROUP} --follow
```

### Batch Resources Not Found

**Error**: `Warning: No outputs found`

**Solution**: Deploy Batch infrastructure:
```bash
cd terraform
terraform apply
```

### Job Fails to Start

**Causes**: ECR image not found, IAM permissions, subnet configuration

**Debug**:
```bash
# Check compute environment
aws batch describe-compute-environments \
  --compute-environments $(cd terraform && terraform output -raw cluster_name)-polars-fargate

# Check job definition
aws batch describe-job-definitions \
  --job-definition-name $(cd terraform && terraform output -raw cluster_name)-polars-tpch

# Check logs
./scripts/batch_helper.sh logs <JOB_ID>
```

### S3 Access Denied

**Solution**: Verify IAM role has S3 permissions:
```bash
ROLE_NAME=$(cd terraform && terraform output -raw cluster_name)-batch-job-role
aws iam get-role-policy --role-name ${ROLE_NAME} --policy-name ${ROLE_NAME}-s3-policy
```

## Cost Analysis

### Fargate Pricing (us-east-1)

- **vCPU**: $0.04048 per vCPU-hour
- **Memory**: $0.004445 per GB-hour

### Example Costs

| Config | Cost/Hour | Cost/5min Job |
|--------|-----------|---------------|
| 4 vCPU, 16 GB | $0.233 | $0.019 |
| 8 vCPU, 32 GB | $0.466 | $0.039 |

### Cost Comparison

| Resource | EKS (Always On) | Batch (On-Demand) |
|----------|-----------------|-------------------|
| Control Plane | $0.10/hour | $0 |
| Nodes (2x m6i.xlarge) | $0.384/hour | $0 |
| Compute (per job) | Included | $0.23/hour |
| **Idle Cost** | **$0.484/hour** | **$0** |
| **Per Job (5 min)** | **$0.04** | **$0.02** |

## Implementation Details

### TPC-H Query 3 (Shipping Priority)

```sql
SELECT
    l.l_orderkey,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS revenue,
    o.o_orderdate,
    o.o_shippriority
FROM customer c
INNER JOIN orders o ON c.c_custkey = o.o_custkey
INNER JOIN lineitem l ON o.o_orderkey = l.l_orderkey
WHERE
    c.c_mktsegment = 'BUILDING'
    AND o.o_orderdate < DATE '1995-03-15'
    AND l.l_shipdate > DATE '1995-03-15'
GROUP BY l.l_orderkey, o.o_orderdate, o.o_shippriority
ORDER BY revenue DESC, o.o_orderdate
LIMIT 10
```

### Metrics Collected

```json
{
  "framework": "polars_duckdb",
  "scale_factor": 10,
  "startup_time": 2.5,
  "execution_time": 15.3,
  "peak_memory_mb": 1024,
  "avg_memory_mb": 768,
  "optimization_metrics": {
    "predicate_pushdown_enabled": true,
    "projection_pushdown_enabled": true,
    "zero_copy_enabled": true,
    "streaming_capable": true
  }
}
```

## Cleanup

```bash
# Cancel running jobs
./scripts/batch_helper.sh cancel <JOB_ID>

# Destroy infrastructure
cd terraform
terraform destroy

# Verify cleanup
aws batch describe-compute-environments \
  --compute-environments $(terraform output -raw cluster_name)-polars-fargate
```

## Files Reference

- **Implementation**: `src/etl/polars_etl_tpch.py`
- **Dockerfile**: `Dockerfile.polars-tpch`
- **Terraform**: `terraform/batch.tf`, `terraform/outputs.tf`
- **Helper Script**: `scripts/batch_helper.sh`
- **Job Definition**: `terraform/polars-tpch-job-definition.json`

## When to Use

**Polars + DuckDB on Batch is ideal for**:
- Datasets up to 100 GB
- Complex analytical queries
- Cost-sensitive workloads
- Fast iteration and development
- Serverless/on-demand compute

**Spark on EKS is better for**:
- Datasets > 100 GB
- Distributed processing requirements
- Existing Spark ecosystem
- Multi-stage pipelines
- Always-on workloads

## References

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Polars Documentation](https://pola-rs.github.io/polars/)
- [AWS Batch Documentation](https://docs.aws.amazon.com/batch/)
- [TPC-H Benchmark](http://www.tpc.org/tpch/)
