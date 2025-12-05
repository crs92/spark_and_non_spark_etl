# ETL Benchmark Terraform Infrastructure

This directory contains Terraform configurations for deploying the ETL benchmark infrastructure on AWS.

## Architecture

The infrastructure includes:

- **VPC**: Multi-AZ VPC with public and private subnets across 3 availability zones
- **EKS Cluster**: Kubernetes v1.28+ cluster with two node groups:
  - Spark workers: r6i.2xlarge instances (8 vCPU, 64GB RAM)
  - Polars workers: r6i.8xlarge instances (32 vCPU, 256GB RAM)
- **S3 Bucket**: Data storage with versioning and intelligent tiering
- **ECR Repositories**: Container image storage for spark-etl and polars-etl
- **IAM Roles**: Service account roles with S3 access for workloads

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.0 installed
3. kubectl installed for cluster access

## Quick Start

1. **Copy the example variables file:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit terraform.tfvars with your settings:**
   ```bash
   vim terraform.tfvars
   ```

3. **Initialize Terraform:**
   ```bash
   make tf-init
   ```

4. **Review the plan:**
   ```bash
   make tf-plan
   ```

5. **Apply the infrastructure:**
   ```bash
   make tf-apply
   ```

6. **Configure kubectl:**
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name etl-benchmark-cluster
   ```

## Makefile Targets

- `make tf-init` - Initialize Terraform working directory
- `make tf-plan` - Generate and show execution plan
- `make tf-apply` - Apply the Terraform configuration
- `make tf-destroy` - Destroy all managed infrastructure
- `make tf-output` - Show Terraform outputs
- `make tf-validate` - Validate Terraform configuration

## Module Structure

```
terraform/
├── main.tf              # Root module configuration
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── terraform.tfvars     # Variable values (create from .example)
└── modules/
    ├── vpc/            # VPC with subnets, NAT gateways, route tables
    ├── eks/            # EKS cluster with node groups
    ├── s3/             # S3 bucket with lifecycle policies
    ├── ecr/            # ECR repositories
    └── iam/            # IAM roles for service accounts (IRSA)
```

## Configuration

### VPC Configuration

The VPC is configured with:
- CIDR: 10.0.0.0/16 (configurable)
- 3 public subnets (for NAT gateways and load balancers)
- 3 private subnets (for EKS nodes)
- NAT gateways in each AZ for high availability
- Internet gateway for public subnet access

### EKS Node Groups

**Spark Workers:**
- Instance type: r6i.2xlarge (8 vCPU, 64GB RAM)
- Min/Max/Desired: 2/10/2 nodes
- Labels: workload=spark, role=worker

**Polars Workers:**
- Instance type: r6i.8xlarge (32 vCPU, 256GB RAM)
- Min/Max/Desired: 0/2/0 nodes (scales from zero)
- Labels: workload=polars, role=worker

### S3 Bucket

- Versioning enabled
- Server-side encryption (AES256)
- Intelligent tiering for cost optimization
- Public access blocked
- Lifecycle policy to clean up old versions after 90 days

### ECR Repositories

- Image scanning on push enabled
- Lifecycle policies:
  - Keep last 10 tagged images
  - Remove untagged images after 7 days

### IAM Roles

Two service account roles are created with:
- S3 read/write access to the benchmark bucket
- CloudWatch Logs access for monitoring
- IRSA (IAM Roles for Service Accounts) integration

## Outputs

After applying, Terraform will output:

- `cluster_name` - EKS cluster name
- `cluster_endpoint` - EKS API endpoint
- `s3_bucket_name` - S3 bucket for data storage
- `ecr_repository_urls` - ECR repository URLs for pushing images
- `spark_service_account_role_arn` - IAM role ARN for Spark pods
- `polars_service_account_role_arn` - IAM role ARN for Polars pods
- `configure_kubectl` - Command to configure kubectl

## Cost Estimation

Approximate monthly costs (us-east-1):

- EKS Control Plane: $73/month
- Spark Workers (2x r6i.2xlarge): ~$730/month
- Polars Workers (0-2x r6i.8xlarge): $0-$2,920/month (when scaled up)
- NAT Gateways (3): ~$100/month
- S3 Storage: Variable based on data size
- Data Transfer: Variable based on usage

**Total baseline cost: ~$900/month** (without Polars workers)

## Cleanup

To destroy all infrastructure:

```bash
make tf-destroy
```

**Warning:** This will delete all resources including the S3 bucket and its contents.

## Security Considerations

- All node groups are in private subnets
- S3 bucket has public access blocked
- IAM roles follow least privilege principle
- EKS cluster logs are enabled for audit trail
- ECR images are scanned for vulnerabilities

## Troubleshooting

### EKS Cluster Access Issues

If you can't access the cluster:
```bash
aws eks update-kubeconfig --region us-east-1 --name etl-benchmark-cluster
kubectl get nodes
```

### Node Group Not Scaling

Check the node group status:
```bash
aws eks describe-nodegroup --cluster-name etl-benchmark-cluster --nodegroup-name etl-benchmark-cluster-spark-workers
```

### S3 Access Issues

Verify the IAM role has correct permissions:
```bash
aws iam get-role --role-name etl-benchmark-cluster-spark-sa-role
```

## Next Steps

After infrastructure is deployed:

1. Install Spark Operator (see task 11.1)
2. Build and push container images to ECR (see task 12)
3. Update ETL code for S3 compatibility (see task 13)
4. Run benchmarks on EKS (see task 15)
