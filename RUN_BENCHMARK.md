# How to Run the NYC Taxi ETL Benchmark

## Prerequisites

1. **AWS Credentials**: Ensure your AWS SSO session is active
   ```bash
   aws sso login
   ```

2. **Infrastructure**: EC2 and EKS must be deployed
   ```bash
   cd terraform
   terraform apply
   ```

3. **Docker Images**: Both images must be pushed to ECR
   ```bash
   make ecr-push-polars  # Polars image for EC2
   make ecr-push-spark   # Spark image for EKS
   ```

4. **Spark Operator**: Must be installed on EKS
   ```bash
   make spark-operator-install
   ```

## Quick Start

### Run Full Benchmark (EC2 + EKS)
```bash
python scripts/run_full_benchmark.py --sizes tiny
```

### Run Only EC2 (Polars)
```bash
python scripts/run_full_benchmark.py --ec2-only --sizes tiny,small
```

### Run Only EKS (Spark)
```bash
python scripts/run_full_benchmark.py --eks-only --sizes tiny,small
```

### Run Multiple Sizes
```bash
python scripts/run_full_benchmark.py --sizes tiny,small,medium
```

## Data Sizes

| Size    | Time Period | Records | Size   | Executors |
|---------|-------------|---------|--------|-----------|
| tiny    | 1 month     | ~3M     | 100MB  | 2         |
| small   | 3 months    | ~9M     | 300MB  | 3         |
| medium  | 6 months    | ~18M    | 600MB  | 5         |
| large   | 12 months   | ~36M    | 1.2GB  | 10        |
| xlarge  | 24 months   | ~72M    | 2.4GB  | 20        |
| xxlarge | 36 months   | ~108M   | 3.6GB  | 30        |

## Monitoring

### EC2 (Polars) Monitoring

**Check SSM Commands**:
```bash
aws ssm list-commands --region eu-central-1 --max-items 5
```

**Get Command Output**:
```bash
aws ssm get-command-invocation \
  --command-id <COMMAND_ID> \
  --instance-id i-013b6270ff17e695f \
  --region eu-central-1
```

**View EC2 Logs**:
```bash
aws ssm start-session --target i-013b6270ff17e695f --region eu-central-1
# Then on the instance:
tail -f /var/log/polars-etl/benchmark.log
```

**Check Docker Containers**:
```bash
aws ssm send-command \
  --instance-ids i-013b6270ff17e695f \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker ps -a"]' \
  --region eu-central-1
```

### EKS (Spark) Monitoring

**List Spark Applications**:
```bash
kubectl get sparkapplication
```

**Watch Spark Application**:
```bash
kubectl get sparkapplication spark-nyc-taxi-tiny -w
```

**Check Application Status**:
```bash
kubectl describe sparkapplication spark-nyc-taxi-tiny
```

**View Driver Logs**:
```bash
kubectl logs spark-nyc-taxi-tiny-driver
```

**View Executor Logs**:
```bash
kubectl logs spark-nyc-taxi-tiny-<executor-id>
```

**List All Pods**:
```bash
kubectl get pods -l app=spark-nyc-taxi-driver
kubectl get pods -l app=spark-nyc-taxi-executor
```

## Results

### Benchmark Results
Results are saved to: `benchmark_results/full_benchmark_results_<timestamp>.json`

Example:
```json
{
  "timestamp": "20251207_143000",
  "data_sizes": ["tiny"],
  "results": [
    {
      "config": {
        "data_size": "tiny",
        "environment": "ec2",
        "instance_type": "r6i.2xlarge"
      },
      "success": true,
      "execution_time": 45.2
    }
  ]
}
```

### CloudWatch Metrics
Collect metrics after benchmarks complete:
```bash
python scripts/collect_cloudwatch_metrics.py
```

### Validate Results
Verify data quality and completeness:
```bash
python scripts/validate_results.py
```

### Cost Analysis
Calculate costs for each benchmark:
```bash
python scripts/analyze_benchmark_costs.py
```

### Generate Report
Create comprehensive benchmark report:
```bash
python scripts/generate_benchmark_report.py
```

## Troubleshooting

### EC2 Issues

**Problem**: "Command not found: run-polars-benchmark.sh"
- **Solution**: Script is now at `/usr/local/bin/run-polars-benchmark.sh` (fixed in orchestration script)

**Problem**: "Docker image not found"
- **Solution**: Rebuild and push image: `make ecr-push-polars`

**Problem**: "Cannot connect to EC2 instance"
- **Solution**: Use SSM (no SSH key needed): `aws ssm start-session --target i-013b6270ff17e695f`

### EKS Issues

**Problem**: "SparkApplication CRD not found"
- **Solution**: Install Spark Operator: `make spark-operator-install`

**Problem**: "Image pull error"
- **Solution**: Rebuild and push image: `make ecr-push-spark`

**Problem**: "Pod Identity authentication failed"
- **Solution**: Verify service account: `kubectl describe sa spark-sa`

### AWS Credentials

**Problem**: "SSO session expired"
- **Solution**: Refresh credentials: `aws sso login`

**Problem**: "Access denied to ECR"
- **Solution**: Check IAM roles have ECR permissions

## Cleanup

### Stop Running Benchmarks
```bash
# Stop Spark applications
kubectl delete sparkapplication --all

# Cancel SSM commands
aws ssm cancel-command --command-id <COMMAND_ID> --region eu-central-1
```

### Destroy Infrastructure
```bash
# Simple cleanup (keeps S3 data)
bash scripts/cleanup_aws_simple.sh

# Full cleanup (deletes everything including S3)
bash scripts/cleanup_aws.sh
```

## Architecture

### EC2 (Polars) - Vertical Scaling
- Single large instance (r6i.2xlarge: 8 vCPU, 64GB RAM)
- Docker container running Polars ETL
- Optimized for in-memory processing
- Best for: Single-node performance, memory-intensive operations

### EKS (Spark) - Horizontal Scaling
- Multiple smaller containers distributed across nodes
- Spark driver + multiple executors
- Optimized for distributed processing
- Best for: Large datasets, parallel processing, fault tolerance

## Current Infrastructure

- **EC2 Instance**: i-013b6270ff17e695f (r6i.2xlarge)
- **EKS Cluster**: etl-benchmark-cluster
- **S3 Bucket**: etl-benchmark-data-764738119924
- **Region**: eu-central-1
- **Architecture**: AMD64

## Makefile Targets

```bash
# Infrastructure
make terraform-init          # Initialize Terraform
make terraform-plan          # Plan infrastructure changes
make terraform-apply         # Deploy infrastructure
make terraform-destroy       # Destroy infrastructure

# Docker Images
make ecr-login              # Login to ECR
make ecr-push-polars        # Build and push Polars image
make ecr-push-spark         # Build and push Spark image

# Spark Operator
make spark-operator-install # Install Spark Operator on EKS
make spark-operator-status  # Check Spark Operator status

# Benchmarks
make benchmark-tiny         # Run tiny benchmark
make benchmark-small        # Run small benchmark
make benchmark-full         # Run all benchmarks

# Analysis
make collect-metrics        # Collect CloudWatch metrics
make validate-results       # Validate benchmark results
make analyze-costs          # Analyze costs
make generate-report        # Generate full report

# Cleanup
make cleanup-simple         # Simple cleanup
make cleanup-full           # Full cleanup
```
