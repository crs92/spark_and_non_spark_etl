# ETL Benchmark: Spark vs Polars on AWS

Benchmark comparing vertical scaling (Polars on EC2) vs horizontal scaling (Spark on EKS) for NYC Taxi data processing.

## Quick Start

### Prerequisites
- AWS CLI configured
- Terraform installed
- kubectl installed
- Python 3.11+

### 1. Deploy Infrastructure
```bash
cd terraform
terraform init
terraform apply
```

### 2. Configure kubectl
```bash
aws eks update-kubeconfig --region eu-central-1 --name etl-benchmark-cluster
```

### 3. Fix Spark Operator (REQUIRED - see CURRENT_ISSUE_AND_SOLUTION.md)
```bash
# Downgrade to stable version
helm uninstall spark-operator -n spark-operator
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm install spark-operator spark-operator/spark-operator \
  --namespace spark-operator \
  --create-namespace \
  --set webhook.enable=true \
  --set image.tag=v1beta2-1.3.8-3.1.1
```

### 4. Build and Push Docker Image
```bash
bash build_on_ec2_fixed.sh
```

### 5. Run Benchmark
```bash
# Test with tiny dataset first
kubectl apply -f k8s/spark-nyc-taxi-tiny-simple.yaml
kubectl get sparkapplication spark-nyc-taxi-tiny -w

# Run full benchmark
python scripts/run_full_benchmark.py --eks-only --sizes tiny,small,medium
```

## Architecture

- **EKS Cluster**: ARM64 Graviton nodes (m7g.large)
- **EC2 Instance**: ARM64 for Docker builds (r7g.2xlarge)
- **Data**: NYC Taxi data localized to `s3://ccorsetti/nyc-taxi/`
- **Regions**: eu-central-1

## Key Files

### Documentation
- `STATUS_FOR_BOSS.md` - High-level project status
- `QUICK_START.md` - 30-minute fix guide
- `CHECKLIST.md` - Step-by-step checklist
- `CURRENT_ISSUE_AND_SOLUTION.md` - Technical details
- `VERIFY_PERMISSIONS.md` - EC2 ECR permissions check
- `POLARS_ALIGNMENT_TODO.md` - Polars implementation alignment

### Code
- `Dockerfile.spark.ec2` - ARM64 Spark image
- `build_on_ec2_fixed.sh` - Build script using EC2
- `k8s/spark-nyc-taxi-tiny-simple.yaml` - Simplified Spark manifest
- `terraform/` - Infrastructure as code
- `src/etl/` - ETL implementations (Spark & Polars)

## Data Sizes

- **tiny**: 36.4 MiB (1 month, 2022-01)
- **small**: 36.4 MiB (1 month, 2022-01)
- **medium**: 586.6 MiB (12 months, 2022)
- **large**: 3.9 GiB (60 months, 2018-2022)

## Troubleshooting

See `CURRENT_ISSUE_AND_SOLUTION.md` for the current Spark Operator issue and solution.

## Cleanup
```bash
cd terraform
terraform destroy
```

Note: S3 data in `s3://ccorsetti` persists after destroy.
