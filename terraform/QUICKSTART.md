# Quick Start Guide - AWS EKS Infrastructure

This guide will help you deploy the ETL benchmark infrastructure to AWS in under 30 minutes.

## Prerequisites Checklist

- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Terraform >= 1.0 installed
- [ ] kubectl installed
- [ ] AWS account with appropriate permissions (EC2, EKS, S3, ECR, IAM)
- [ ] Sufficient AWS service limits (EKS clusters, VPCs, Elastic IPs)

## Step-by-Step Deployment

### 1. Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` to customize your deployment:

```hcl
aws_region      = "us-east-1"  # Change to your preferred region
environment     = "dev"
cluster_name    = "etl-benchmark-cluster"
cluster_version = "1.28"

# Adjust node group sizes based on your needs
spark_workers_config = {
  instance_type = "r6i.2xlarge"
  min_size      = 2
  max_size      = 10
  desired_size  = 2
}

polars_workers_config = {
  instance_type = "r6i.8xlarge"
  min_size      = 0
  max_size      = 2
  desired_size  = 0  # Start with 0, scale up when needed
}
```

### 2. Initialize Terraform

```bash
make tf-init
```

This will:
- Download required provider plugins (AWS, Kubernetes, TLS)
- Initialize the working directory
- Create a lock file for provider versions

### 3. Review the Plan

```bash
make tf-plan
```

Review the resources that will be created:
- VPC with 3 public and 3 private subnets
- EKS cluster with 2 node groups
- S3 bucket for data storage
- 2 ECR repositories
- IAM roles and policies

Expected resource count: ~50-60 resources

### 4. Deploy Infrastructure

```bash
make tf-apply
```

Type `yes` when prompted to confirm.

**Deployment time: ~15-20 minutes**

The EKS cluster creation is the longest step (~10-15 minutes).

### 5. Configure kubectl

After deployment completes, configure kubectl to access your cluster:

```bash
aws eks update-kubeconfig --region us-east-1 --name etl-benchmark-cluster
```

Verify cluster access:

```bash
kubectl get nodes
```

You should see your Spark worker nodes listed.

### 6. View Outputs

```bash
make tf-output
```

Important outputs:
- `s3_bucket_name` - Use this for data storage
- `ecr_repository_urls` - Use these for pushing Docker images
- `spark_service_account_role_arn` - IAM role for Spark pods
- `polars_service_account_role_arn` - IAM role for Polars pods

## Next Steps

### Install Spark Operator

```bash
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm repo update

helm install spark-operator spark-operator/spark-operator \
  --namespace spark-operator \
  --create-namespace \
  --set webhook.enable=true
```

### Create Kubernetes Service Accounts

```bash
# Create Spark service account
kubectl create serviceaccount spark-sa

# Annotate with IAM role
kubectl annotate serviceaccount spark-sa \
  eks.amazonaws.com/role-arn=$(terraform output -raw spark_service_account_role_arn)

# Create Polars service account
kubectl create serviceaccount polars-sa

kubectl annotate serviceaccount polars-sa \
  eks.amazonaws.com/role-arn=$(terraform output -raw polars_service_account_role_arn)
```

### Build and Push Docker Images

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $(terraform output -raw registry_id).dkr.ecr.us-east-1.amazonaws.com

# Build and push Spark image
docker build -f Dockerfile.spark -t spark-etl:latest .
docker tag spark-etl:latest $(terraform output -json ecr_repository_urls | jq -r '.["spark-etl"]'):latest
docker push $(terraform output -json ecr_repository_urls | jq -r '.["spark-etl"]'):latest

# Build and push Polars image
docker build -f Dockerfile.pythonic -t polars-etl:latest .
docker tag polars-etl:latest $(terraform output -json ecr_repository_urls | jq -r '.["polars-etl"]'):latest
docker push $(terraform output -json ecr_repository_urls | jq -r '.["polars-etl"]'):latest
```

## Cost Management

### Monitor Costs

```bash
# Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=2024-12-01,End=2024-12-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://cost-filter.json
```

### Scale Down When Not in Use

```bash
# Scale Spark workers to 0
kubectl scale deployment spark-workers --replicas=0

# Or update Terraform
# Set desired_size = 0 in terraform.tfvars
make tf-apply
```

### Destroy Infrastructure

When you're done with testing:

```bash
make tf-destroy
```

**⚠️ WARNING:** This will delete all resources including the S3 bucket and data!

## Troubleshooting

### Issue: EKS cluster creation fails

**Solution:** Check AWS service limits:
```bash
aws service-quotas list-service-quotas \
  --service-code eks \
  --query 'Quotas[?QuotaName==`Clusters`]'
```

### Issue: Node group fails to create

**Solution:** Check EC2 instance limits:
```bash
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-1216C47A
```

### Issue: Can't access cluster with kubectl

**Solution:** Update kubeconfig and check IAM permissions:
```bash
aws eks update-kubeconfig --region us-east-1 --name etl-benchmark-cluster
kubectl auth can-i get pods --all-namespaces
```

### Issue: Pods can't access S3

**Solution:** Verify IRSA configuration:
```bash
# Check service account annotation
kubectl describe serviceaccount spark-sa

# Check pod environment
kubectl describe pod <pod-name> | grep AWS
```

## Estimated Costs

Based on us-east-1 pricing (as of 2024):

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| EKS Control Plane | 1 cluster | $73 |
| Spark Workers | 2x r6i.2xlarge | $730 |
| Polars Workers | 0-2x r6i.8xlarge | $0-$2,920 |
| NAT Gateways | 3 gateways | $100 |
| S3 Storage | Variable | ~$23/TB |
| Data Transfer | Variable | ~$90/TB |

**Baseline cost (Spark only): ~$900/month**

**With Polars workers: ~$3,800/month**

### Cost Optimization Tips

1. Use Spot Instances (60-90% savings)
2. Scale to zero when not in use
3. Use S3 Intelligent Tiering
4. Enable EKS cluster autoscaling
5. Set up budget alerts in AWS Cost Explorer

## Support

For issues or questions:
1. Check the main [README.md](README.md)
2. Review Terraform documentation
3. Check AWS EKS documentation
4. Open an issue in the project repository
