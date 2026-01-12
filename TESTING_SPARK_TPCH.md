# Testing Spark TPC-H ETL on EKS

This guide walks you through testing the Spark TPC-H ETL implementation on AWS EKS.

## Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0
- kubectl
- Docker or Podman (podman is automatically detected)
- helm
- Python 3.12+ with dependencies installed

**Note**: The scripts automatically detect whether you're using Docker or Podman. If you have podman installed, it will be used automatically.

## Option 1: Full Deployment (From Scratch)

Use this if you don't have EKS infrastructure deployed yet.

### Step 1: Deploy Infrastructure

```bash
# Full automated deployment
./scripts/deploy_and_test_spark_tpch.sh
```

This script will:
1. ✅ Check prerequisites
2. ✅ Deploy EKS cluster with Terraform (~15-20 min)
3. ✅ Configure kubectl
4. ✅ Install Spark Operator
5. ✅ Setup Kubernetes RBAC
6. ✅ Generate TPC-H data (if not exists)
7. ✅ Build and push Docker image
8. ✅ Run Spark TPC-H job
9. ✅ Display results

### Step 2: Review Results

Results are automatically displayed at the end. You can also check:

```bash
# View S3 results
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 ls s3://etl-benchmark-data-${ACCOUNT_ID}/results/spark/sf10/ --recursive

# Download metrics
aws s3 cp s3://etl-benchmark-data-${ACCOUNT_ID}/results/spark/sf10/metrics_*.json ./metrics.json
cat metrics.json
```

## Option 2: Quick Test (Infrastructure Already Deployed)

Use this if you already have EKS cluster and just want to test the Spark ETL.

### Step 1: Ensure kubectl is configured

```bash
aws eks update-kubeconfig --region eu-central-1 --name etl-benchmark-cluster
kubectl get nodes
```

### Step 2: Run quick test

```bash
# Test with Scale Factor 10 (default)
./scripts/quick_test_spark_tpch.sh

# Test with Scale Factor 100
./scripts/quick_test_spark_tpch.sh 100
```

This script will:
1. ✅ Build and push Docker image
2. ✅ Submit Spark job
3. ✅ Monitor job execution
4. ✅ Display results

## Option 3: Manual Step-by-Step

### Step 1: Generate TPC-H Data

```bash
# Generate SF10 data (~10GB)
python src/generation/generate_tpch_data_fast.py \
    --scale-factor 10 \
    --output-dir data/tpch-sf10 \
    --s3-bucket s3://etl-benchmark-data-$(aws sts get-caller-identity --query Account --output text) \
    --s3-prefix tpch-sf10
```

### Step 2: Build and Push Docker Image

```bash
# Get account ID and ECR registry
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=eu-central-1
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ECR login
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

# Build image
docker build -f Dockerfile.spark -t spark-etl:latest .

# Tag and push
docker tag spark-etl:latest ${ECR_REGISTRY}/spark-etl:latest
docker push ${ECR_REGISTRY}/spark-etl:latest
```

### Step 3: Submit Spark Job

```bash
# Submit SF10 job
kubectl apply -f k8s/spark-tpch-sf10.yaml

# Monitor job status
kubectl get sparkapplications spark-tpch-sf10 -w
```

### Step 4: View Logs

```bash
# Wait for driver pod to be created
kubectl wait --for=condition=Ready pod/spark-tpch-sf10-driver --timeout=300s

# Follow driver logs
kubectl logs -f spark-tpch-sf10-driver

# View executor logs (optional)
kubectl get pods -l app=spark-tpch-executor
kubectl logs spark-tpch-sf10-<executor-id>
```

### Step 5: Check Results

```bash
# List results in S3
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 ls s3://etl-benchmark-data-${ACCOUNT_ID}/results/spark/sf10/ --recursive

# Download and view metrics
aws s3 cp s3://etl-benchmark-data-${ACCOUNT_ID}/results/spark/sf10/metrics_*.json ./metrics.json
cat metrics.json | python -m json.tool
```

## Troubleshooting

### Issue: Docker build fails

**Solution**: Ensure you're in the project root directory:
```bash
cd /path/to/spark_and_non_spark_etl
docker build -f Dockerfile.spark -t spark-etl:latest .
```

### Issue: kubectl can't connect to cluster

**Solution**: Update kubeconfig:
```bash
aws eks update-kubeconfig --region eu-central-1 --name etl-benchmark-cluster
```

### Issue: Spark job fails with S3 access denied

**Solution**: Verify Pod Identity is configured:
```bash
# Check service account
kubectl describe serviceaccount spark-sa

# Check pod identity association
aws eks list-pod-identity-associations \
    --cluster-name etl-benchmark-cluster \
    --region eu-central-1
```

### Issue: TPC-H data not found

**Solution**: Generate data first:
```bash
python src/generation/generate_tpch_data_fast.py \
    --scale-factor 10 \
    --s3-bucket s3://etl-benchmark-data-$(aws sts get-caller-identity --query Account --output text) \
    --s3-prefix tpch-sf10
```

### Issue: Driver pod stuck in Pending

**Solution**: Check node resources:
```bash
kubectl describe pod spark-tpch-sf10-driver
kubectl get nodes
kubectl top nodes
```

### Issue: Out of memory errors

**Solution**: Increase executor memory in manifest:
```yaml
executor:
  memory: "8g"  # Increase from 4g
```

## Monitoring and Debugging

### View all Spark resources

```bash
kubectl get sparkapplications
kubectl get pods -l app=spark-tpch-driver
kubectl get pods -l app=spark-tpch-executor
```

### Check Spark Operator logs

```bash
kubectl logs -n spark-operator -l app.kubernetes.io/name=spark-operator
```

### View CloudWatch logs

```bash
# Get log group
aws logs describe-log-groups --log-group-name-prefix /aws/eks/etl-benchmark

# Tail logs
aws logs tail /aws/eks/etl-benchmark-cluster/cluster --follow
```

### Check resource usage

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods
```

## Performance Metrics

The Spark ETL tracks these metrics:

- **startup_time**: Time from job submission to execution start
- **execution_time**: Time from data read to result write
- **peak_memory_mb**: Maximum memory usage
- **bytes_read**: Data read from S3
- **bytes_written**: Data written to S3
- **spark_app_id**: Spark application ID

Example metrics output:
```json
{
  "framework": "spark",
  "startup_time": 45.2,
  "execution_time": 187.5,
  "peak_memory_mb": 12288,
  "bytes_read": 10737418240,
  "bytes_written": 4096,
  "timestamp": "20250111_143022",
  "spark_app_id": "spark-application-1736604622123",
  "scale_factor": 10
}
```

## Cleanup

### Delete Spark job only

```bash
kubectl delete sparkapplication spark-tpch-sf10
```

### Delete all Spark jobs

```bash
kubectl delete sparkapplications --all
```

### Destroy infrastructure

```bash
cd terraform
terraform destroy
```

**⚠️ WARNING**: This will delete all resources including S3 data!

## Cost Estimation

### SF10 Test (~10GB)
- **Duration**: ~5-10 minutes
- **Resources**: 2 cores driver + 8 cores executors = 10 cores
- **Cost**: ~$0.10 per run

### SF100 Test (~100GB)
- **Duration**: ~30-60 minutes
- **Resources**: 4 cores driver + 32 cores executors = 36 cores
- **Cost**: ~$1.50 per run

### Infrastructure (when idle)
- **EKS Control Plane**: $0.10/hour
- **Worker Nodes**: $0.416/hour (2x m6i.large)
- **Total**: ~$0.52/hour or ~$373/month

**Tip**: Scale nodes to 0 when not in use to save costs!

## Next Steps

1. ✅ Test Spark ETL with SF10
2. ✅ Test Spark ETL with SF100
3. ⏭️ Implement Polars/DuckDB ETL (Task 5)
4. ⏭️ Compare performance metrics
5. ⏭️ Generate analysis reports

## Support

For issues:
1. Check logs: `kubectl logs spark-tpch-sf10-driver`
2. Check pod status: `kubectl describe pod spark-tpch-sf10-driver`
3. Review Terraform state: `cd terraform && terraform show`
4. Check AWS console for EKS cluster status
