# Multi-Job Orchestration Module

This module contains components for orchestrating concurrent job execution across EKS and AWS Batch.

## Purpose

Stress-test both PySpark (EKS) and Polars/DuckDB (AWS Batch) implementations by running multiple concurrent jobs and measuring startup latency and performance.

## Key Components

- **JobOrchestrator**: Main class for submitting and monitoring jobs
- EKS job submission via Kubernetes API
- AWS Batch job submission via boto3
- Job monitoring and metrics collection
- Startup latency calculation

## Usage

```python
from src.orchestration.job_orchestrator import JobOrchestrator

# Initialize orchestrator
orchestrator = JobOrchestrator(
    eks_cluster="my-cluster",
    batch_job_queue="my-queue"
)

# Submit jobs
spark_jobs = orchestrator.submit_spark_jobs(count=10)
batch_jobs = orchestrator.submit_batch_jobs(count=10)

# Monitor and collect metrics
all_jobs = spark_jobs + batch_jobs
metrics = orchestrator.monitor_jobs(all_jobs)
```

## Requirements

See `.env.example` for required environment variables:
- `EKS_CLUSTER_NAME`
- `BATCH_JOB_QUEUE`
- `BATCH_JOB_DEFINITION`
- `CONCURRENT_JOBS_COUNT`
