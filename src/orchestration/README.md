# Multi-Job Orchestration Module

This module contains components for orchestrating concurrent job execution across EKS and AWS Batch.

## Purpose

Stress-test both PySpark (EKS) and Polars/DuckDB (AWS Batch) implementations by running multiple concurrent jobs and measuring startup latency and performance.

## Key Components

### JobOrchestrator

Main class for submitting and monitoring jobs across platforms:

- **Job Submission**: Submit multiple jobs concurrently to EKS and AWS Batch
- **Job Monitoring**: Poll job status and record timestamps (created, started, completed)
- **Startup Latency**: Calculate time from job submission to execution start
- **Metrics Collection**: Download execution metrics from S3
- **Aggregation**: Combine metrics across all jobs with summary statistics

### Data Classes

- **JobSubmission**: Represents a submitted job with creation timestamp
- **JobMetrics**: Complete metrics for a job including timing and execution details

## Usage

### Basic Usage

```python
from src.orchestration import JobOrchestrator

# Initialize orchestrator (reads from environment variables)
orchestrator = JobOrchestrator()

# Submit 10 Spark jobs to EKS
spark_jobs = orchestrator.submit_spark_jobs(count=10, scale_factor=10)

# Submit 10 Polars jobs to AWS Batch
batch_jobs = orchestrator.submit_batch_jobs(count=10, scale_factor=10)

# Monitor all jobs
all_jobs = spark_jobs + batch_jobs
metrics = orchestrator.monitor_jobs(all_jobs)

# Calculate startup latency
metrics = orchestrator.calculate_startup_latency(metrics)

# Collect execution metrics from S3
metrics = orchestrator.collect_metrics_from_s3(metrics)

# Save aggregated results
orchestrator.save_aggregated_metrics(metrics, "results.json")
```

### Using the CLI Script

```bash
# Run full benchmark with 10 jobs each
python scripts/run_orchestrated_benchmark.py \
    --spark-jobs 10 \
    --batch-jobs 10 \
    --scale-factor 10

# Run only Spark jobs
python scripts/run_orchestrated_benchmark.py \
    --spark-jobs 10 \
    --skip-batch \
    --scale-factor 10

# Run only Batch jobs
python scripts/run_orchestrated_benchmark.py \
    --batch-jobs 10 \
    --skip-spark \
    --scale-factor 10

# Custom configuration
python scripts/run_orchestrated_benchmark.py \
    --spark-jobs 5 \
    --batch-jobs 5 \
    --scale-factor 100 \
    --poll-interval 10 \
    --max-wait-time 7200 \
    --output s3://my-bucket/metrics/results.json
```

## Configuration

### Required Environment Variables

```bash
# EKS Configuration
EKS_CLUSTER_NAME=my-eks-cluster
K8S_NAMESPACE=default

# AWS Batch Configuration
BATCH_JOB_QUEUE=my-batch-queue
BATCH_JOB_DEFINITION=my-job-definition

# S3 Configuration
S3_BUCKET_NAME=my-tpch-bucket
S3_METRICS_PREFIX=metrics

# AWS Region
AWS_REGION=us-east-1
```

### Optional Environment Variables

```bash
# Job Configuration
CONCURRENT_JOBS_COUNT=10
JOB_POLL_INTERVAL=5
MAX_JOB_WAIT_TIME=3600

# Spark Configuration
SPARK_ECR_IMAGE=123456789.dkr.ecr.us-east-1.amazonaws.com/spark-etl:latest

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

## Architecture

### Job Submission Flow

1. **Create Job Manifest**: Generate SparkApplication (EKS) or Batch job definition
2. **Submit to Platform**: Use Kubernetes API or boto3 to submit
3. **Record Timestamp**: Capture job creation time
4. **Return Submission**: Return JobSubmission object with job ID and metadata

### Job Monitoring Flow

1. **Initialize Metrics**: Create JobMetrics for each submission
2. **Poll Status**: Check job status every N seconds
3. **Record Transitions**: Capture timestamps when job starts and completes
4. **Calculate Latency**: Compute startup latency (started - created)
5. **Return Metrics**: Return complete JobMetrics list

### Metrics Collection Flow

1. **Wait for Completion**: Ensure all jobs are finished
2. **Download from S3**: Fetch metrics JSON for each job
3. **Enrich Metrics**: Add execution details (memory, I/O) to JobMetrics
4. **Aggregate**: Calculate summary statistics by type and platform
5. **Save Results**: Write aggregated metrics to file or S3

## Output Format

### Aggregated Metrics JSON

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "total_jobs": 20,
  "jobs": [
    {
      "job_id": "spark-abc123",
      "job_type": "spark",
      "job_name": "spark-tpch-sf10-20240115-103000-001",
      "platform": "eks",
      "created_at": "2024-01-15T10:30:00Z",
      "started_at": "2024-01-15T10:30:45Z",
      "completed_at": "2024-01-15T10:35:30Z",
      "startup_latency_seconds": 45.0,
      "execution_time_seconds": 285.0,
      "status": "SUCCEEDED",
      "peak_memory_mb": 12288,
      "bytes_read": 10737418240,
      "bytes_written": 1048576
    }
  ],
  "summary": {
    "by_type": {
      "spark": {
        "count": 10,
        "succeeded": 10,
        "failed": 0,
        "startup_latency": {
          "mean": 45.2,
          "min": 42.1,
          "max": 52.3
        },
        "execution_time": {
          "mean": 287.5,
          "min": 275.0,
          "max": 305.0
        }
      },
      "polars": {
        "count": 10,
        "succeeded": 10,
        "failed": 0,
        "startup_latency": {
          "mean": 8.5,
          "min": 7.2,
          "max": 10.1
        },
        "execution_time": {
          "mean": 195.3,
          "min": 185.0,
          "max": 210.0
        }
      }
    }
  }
}
```

## Error Handling

The orchestrator includes comprehensive error handling:

- **Configuration Validation**: Checks required environment variables at initialization
- **API Retries**: Uses boto3 default retry logic for AWS API calls
- **Graceful Degradation**: Continues with successful jobs if some fail
- **Timeout Protection**: Raises TimeoutError if jobs don't complete within max_wait_time
- **Missing Metrics**: Logs warnings but continues if S3 metrics are unavailable

## Testing

Property-based tests validate:

- Concurrent job submission (Property 12)
- Timestamp recording (Property 13)
- Startup latency calculation (Property 14)
- Complete metrics collection (Property 15)

Run tests with:

```bash
pytest tests/ -k orchestrator
```

## Dependencies

- `boto3`: AWS SDK for Batch and S3 operations
- `kubernetes`: Python client for Kubernetes API (Spark Operator)
- `python-dotenv`: Load environment variables from .env files

## Troubleshooting

### Kubernetes Connection Issues

If you see "Failed to load Kubernetes configuration":

1. Ensure `kubectl` is configured: `kubectl cluster-info`
2. Check kubeconfig: `echo $KUBECONFIG`
3. For in-cluster execution, ensure service account has proper RBAC

### AWS Batch Job Submission Failures

If Batch jobs fail to submit:

1. Verify job queue exists: `aws batch describe-job-queues`
2. Check job definition: `aws batch describe-job-definitions`
3. Ensure IAM permissions for `batch:SubmitJob`

### Missing Metrics from S3

If metrics collection fails:

1. Check S3 bucket permissions
2. Verify metrics files are written by jobs: `aws s3 ls s3://bucket/metrics/`
3. Ensure S3_METRICS_PREFIX matches job output configuration

## Performance Considerations

- **Concurrent Submissions**: Jobs are submitted with 0.5s delay to avoid API throttling
- **Polling Interval**: Default 5s balances responsiveness and API load
- **Batch Size**: Tested with up to 50 concurrent jobs per platform
- **Memory Usage**: Orchestrator uses minimal memory (~50MB for 100 jobs)

## Future Enhancements

- [ ] Support for custom job configurations per submission
- [ ] Real-time metrics streaming (CloudWatch integration)
- [ ] Automatic retry for failed jobs
- [ ] Cost estimation during orchestration
- [ ] Web dashboard for live monitoring
