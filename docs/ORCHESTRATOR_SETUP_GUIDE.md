# JobOrchestrator Setup Guide

## Environment Configuration

The JobOrchestrator automatically loads environment variables from a `.env` file in the project root using `python-dotenv`. You don't need to manually export variables!

### Quick Start

1. **Your `.env` file is already configured!** The orchestrator will automatically load it.

2. **Verify your configuration**:
   ```bash
   # Check that key variables are set
   grep -E "EKS_CLUSTER_NAME|BATCH_JOB_QUEUE|S3_BUCKET_NAME" .env
   ```

3. **Run the orchestrator**:
   ```bash
   python scripts/run_orchestrated_benchmark.py --spark-jobs 2 --batch-jobs 2
   ```

## How It Works

### Automatic .env Loading

The orchestrator automatically loads your `.env` file when imported:

```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env from project root
```

This happens in two places:
1. `src/orchestration/job_orchestrator.py` - When the module is imported
2. `scripts/run_orchestrated_benchmark.py` - When the script runs

### Configuration Priority

Environment variables are loaded in this order (later overrides earlier):
1. `.env` file in project root
2. System environment variables (if you export them)
3. Parameters passed to JobOrchestrator constructor

### Example Usage

```python
from src.orchestration import JobOrchestrator

# Option 1: Use .env file (recommended)
orchestrator = JobOrchestrator()
# Reads EKS_CLUSTER_NAME, BATCH_JOB_QUEUE, etc. from .env

# Option 2: Override specific values
orchestrator = JobOrchestrator(
    eks_cluster="my-custom-cluster",  # Overrides EKS_CLUSTER_NAME
    # Other values still come from .env
)

# Option 3: Use system environment variables
# export EKS_CLUSTER_NAME=my-cluster
# orchestrator = JobOrchestrator()
```

## Required Environment Variables

The orchestrator needs these variables (already in your `.env`):

### For Spark Jobs (EKS)
- `EKS_CLUSTER_NAME` - Your EKS cluster name
- `K8S_NAMESPACE` - Kubernetes namespace (default: "default")
- `S3_BUCKET_NAME` - S3 bucket for data and results

### For Polars Jobs (AWS Batch)
- `BATCH_JOB_QUEUE` - AWS Batch job queue name
- `BATCH_JOB_DEFINITION` - AWS Batch job definition name
- `S3_BUCKET_NAME` - S3 bucket for data and results

### General Configuration
- `AWS_REGION` - AWS region (default: "us-east-1")
- `S3_METRICS_PREFIX` - S3 prefix for metrics (default: "metrics")

## Your Current Configuration

Based on your `.env` file:

```bash
# EKS Configuration
EKS_CLUSTER_NAME=tpch-eks-cluster
K8S_NAMESPACE=default

# AWS Batch Configuration
BATCH_JOB_QUEUE=tpch-job-queue
BATCH_JOB_DEFINITION=tpch-batch-job-definition

# S3 Configuration
S3_BUCKET_NAME=ccorsetti
S3_METRICS_PREFIX=metrics

# AWS Region
AWS_REGION=eu-central-1
```

## Testing Your Configuration

### 1. Test Environment Loading

```python
import os
from dotenv import load_dotenv

load_dotenv()

print(f"EKS Cluster: {os.getenv('EKS_CLUSTER_NAME')}")
print(f"Batch Queue: {os.getenv('BATCH_JOB_QUEUE')}")
print(f"S3 Bucket: {os.getenv('S3_BUCKET_NAME')}")
```

### 2. Test Orchestrator Initialization

```python
from src.orchestration import JobOrchestrator

orchestrator = JobOrchestrator()
# Should print configuration details from .env
```

### 3. Dry Run Test

```bash
# Test with minimal jobs
python scripts/run_orchestrated_benchmark.py \
    --spark-jobs 1 \
    --batch-jobs 1 \
    --scale-factor 10
```

## Troubleshooting

### "Configuration not set" warnings

If you see warnings like:
```
WARNING - EKS_CLUSTER_NAME not set - Spark job submission will not work
```

**Solution**: Check that your `.env` file is in the project root and contains the variable:
```bash
# Verify .env location
ls -la .env

# Check variable is set
grep EKS_CLUSTER_NAME .env
```

### Variables not loading

If variables aren't loading from `.env`:

1. **Check file location**: `.env` must be in project root (same directory as `pyproject.toml`)

2. **Check file format**: No spaces around `=`
   ```bash
   # ✅ Correct
   EKS_CLUSTER_NAME=my-cluster

   # ❌ Wrong
   EKS_CLUSTER_NAME = my-cluster
   ```

3. **Check for comments**: Lines starting with `#` are ignored
   ```bash
   # This is a comment
   EKS_CLUSTER_NAME=my-cluster  # This works
   ```

4. **Reload after changes**: If you modify `.env`, restart your Python process

### AWS Credentials

The orchestrator uses boto3's default credential chain:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (if running on EC2/EKS)

You typically don't need to set credentials in `.env` if you have AWS CLI configured:
```bash
aws configure
```

## Advanced Configuration

### Multiple Environments

Use different `.env` files for different environments:

```bash
# Development
cp .env .env.dev

# Production
cp .env .env.prod

# Load specific environment
python -c "from dotenv import load_dotenv; load_dotenv('.env.prod')"
```

### Override from Command Line

You can override `.env` values by exporting environment variables:

```bash
# Override EKS cluster for this run only
export EKS_CLUSTER_NAME=test-cluster
python scripts/run_orchestrated_benchmark.py --spark-jobs 2
```

### Docker/Container Usage

When running in Docker, mount your `.env` file:

```bash
docker run -v $(pwd)/.env:/app/.env my-orchestrator-image
```

Or pass environment variables directly:

```bash
docker run \
    -e EKS_CLUSTER_NAME=my-cluster \
    -e BATCH_JOB_QUEUE=my-queue \
    my-orchestrator-image
```

## Security Best Practices

1. **Never commit `.env` to git**: Already in `.gitignore`

2. **Use IAM roles when possible**: Avoid storing AWS credentials in `.env`

3. **Rotate credentials regularly**: If you must use credentials in `.env`

4. **Use AWS Secrets Manager**: For production deployments

5. **Restrict file permissions**:
   ```bash
   chmod 600 .env
   ```

## Summary

✅ **You're all set!** Your `.env` file is properly configured and will be automatically loaded by the orchestrator.

Just run:
```bash
python scripts/run_orchestrated_benchmark.py --spark-jobs 10 --batch-jobs 10
```

No need to export environment variables manually! 🎉
