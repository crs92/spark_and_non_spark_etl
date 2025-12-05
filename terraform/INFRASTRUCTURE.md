# Infrastructure Overview

This document provides a detailed overview of the AWS infrastructure created by this Terraform configuration.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                          AWS Account                         │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    VPC (10.0.0.0/16)                    │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │   AZ-1       │  │   AZ-2       │  │   AZ-3       │   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │   │ │
│  │  │ │ Public   │ │  │ │ Public   │ │  │ │ Public   │ │   │ │
│  │  │ │ Subnet   │ │  │ │ Subnet   │ │  │ │ Subnet   │ │   │ │
│  │  │ │          │ │  │ │          │ │  │ │          │ │   │ │
│  │  │ │ NAT GW   │ │  │ │ NAT GW   │ │  │ │ NAT GW   │ │   │ │
│  │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │   │ │
│  │  │ │ Private  │ │  │ │ Private  │ │  │ │ Private  │ │   │ │
│  │  │ │ Subnet   │ │  │ │ Subnet   │ │  │ │ Subnet   │ │   │ │
│  │  │ │          │ │  │ │          │ │  │ │          │ │   │ │
│  │  │ │ EKS      │ │  │ │ EKS      │ │  │ │ EKS      │ │   │ │
│  │  │ │ Nodes    │ │  │ │ Nodes    │ │  │ │ Nodes    │ │   │ │
│  │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  │                                                         │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │           EKS Cluster (v1.28+)                     │ │ │
│  │  │                                                    │ │ │
│  │  │  ┌──────────────────┐  ┌──────────────────┐        │ │ │
│  │  │  │ Spark Workers    │  │ Polars Workers   │        │ │ │
│  │  │  │ r6i.2xlarge      │  │ r6i.8xlarge      │        │ │ │
│  │  │  │ 2-10 nodes       │  │ 0-2 nodes        │        │ │ │
│  │  │  └──────────────────┘  └──────────────────┘        │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │   S3 Bucket     │  │  ECR Repos      │  │  IAM Roles   │  │
│  │                 │  │                 │  │              │  │
│  │ etl-benchmark-  │  │ - spark-etl     │  │ - spark-sa   │  │
│  │ data-{account}  │  │ - polars-etl    │  │ - polars-sa  │  │
│  └─────────────────┘  └─────────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Resource Inventory

### VPC Resources

| Resource | Count | Description |
|----------|-------|-------------|
| VPC | 1 | Main VPC with CIDR 10.0.0.0/16 |
| Public Subnets | 3 | One per AZ for NAT gateways and load balancers |
| Private Subnets | 3 | One per AZ for EKS worker nodes |
| Internet Gateway | 1 | Provides internet access for public subnets |
| NAT Gateways | 3 | One per AZ for high availability |
| Elastic IPs | 3 | One per NAT gateway |
| Route Tables | 4 | 1 public, 3 private (one per AZ) |

**Total VPC Resources: ~20**

### EKS Resources

| Resource | Count | Description |
|----------|-------|-------------|
| EKS Cluster | 1 | Kubernetes v1.28+ cluster |
| Node Groups | 2 | Spark workers and Polars workers |
| IAM Roles | 2 | Cluster role and node role |
| Security Groups | 1 | Cluster security group |
| OIDC Provider | 1 | For IRSA (IAM Roles for Service Accounts) |

**Node Group Details:**

**Spark Workers:**
- Instance Type: r6i.2xlarge (8 vCPU, 64GB RAM)
- Min/Max/Desired: 2/10/2 nodes
- Labels: workload=spark, role=worker
- Purpose: Distributed Spark processing

**Polars Workers:**
- Instance Type: r6i.8xlarge (32 vCPU, 256GB RAM)
- Min/Max/Desired: 0/2/0 nodes
- Labels: workload=polars, role=worker
- Purpose: High-memory single-node processing

**Total EKS Resources: ~15**

### S3 Resources

| Resource | Description |
|----------|-------------|
| S3 Bucket | etl-benchmark-data-{account_id} |
| Versioning | Enabled |
| Encryption | AES256 server-side encryption |
| Lifecycle Rules | Intelligent tiering + version cleanup |
| Public Access | Blocked |

**Bucket Structure:**
```
s3://etl-benchmark-data-{account_id}/
├── input/
│   ├── small/
│   │   ├── bulk/
│   │   └── incremental/
│   ├── medium/
│   ├── large/
│   └── xlarge/
└── output/
    ├── spark/
    └── polars/
```

**Total S3 Resources: ~5**

### ECR Resources

| Repository | Purpose |
|------------|---------|
| spark-etl | Spark ETL Docker images |
| polars-etl | Polars ETL Docker images |

**Features:**
- Image scanning on push
- Lifecycle policies (keep last 10 tagged images)
- Automatic cleanup of untagged images after 7 days

**Total ECR Resources: ~4**

### IAM Resources

| Resource | Purpose |
|----------|---------|
| spark-sa-role | IAM role for Spark service account |
| polars-sa-role | IAM role for Polars service account |
| s3-access-policy | S3 read/write permissions |
| cloudwatch-logs-policy | CloudWatch Logs permissions |

**Permissions:**
- S3: GetObject, PutObject, DeleteObject, ListBucket
- CloudWatch: CreateLogGroup, CreateLogStream, PutLogEvents
- IRSA: AssumeRoleWithWebIdentity for pod authentication

**Total IAM Resources: ~8**

## Total Resource Count

**Approximate total: 50-60 AWS resources**

## Network Configuration

### CIDR Allocation

| Subnet Type | AZ | CIDR Block | Available IPs |
|-------------|-----|------------|---------------|
| Public | us-east-1a | 10.0.0.0/20 | 4,091 |
| Public | us-east-1b | 10.0.16.0/20 | 4,091 |
| Public | us-east-1c | 10.0.32.0/20 | 4,091 |
| Private | us-east-1a | 10.0.48.0/20 | 4,091 |
| Private | us-east-1b | 10.0.64.0/20 | 4,091 |
| Private | us-east-1c | 10.0.80.0/20 | 4,091 |

**Total Available IPs: ~24,000**

### Routing

**Public Subnets:**
- Default route (0.0.0.0/0) → Internet Gateway
- Used for NAT gateways and load balancers

**Private Subnets:**
- Default route (0.0.0.0/0) → NAT Gateway (per AZ)
- Used for EKS worker nodes
- Outbound internet access via NAT gateway
- No inbound internet access

## Security Configuration

### Network Security

1. **Private Subnets Only**: All EKS nodes run in private subnets
2. **No Public IPs**: Worker nodes have no public IP addresses
3. **NAT Gateway**: Outbound internet access for package downloads
4. **Security Groups**: Cluster security group controls pod-to-pod communication

### IAM Security

1. **IRSA**: IAM Roles for Service Accounts (no static credentials)
2. **Least Privilege**: Minimal permissions for each role
3. **Separate Roles**: Different roles for Spark and Polars workloads
4. **Audit Trail**: CloudWatch Logs for all API calls

### S3 Security

1. **Encryption**: Server-side encryption enabled
2. **Versioning**: Enabled for data recovery
3. **Public Access**: Blocked at bucket level
4. **SSL Only**: Bucket policy enforces HTTPS

### ECR Security

1. **Image Scanning**: Automatic vulnerability scanning
2. **Encryption**: Images encrypted at rest
3. **Lifecycle Policies**: Automatic cleanup of old images

## High Availability

### Multi-AZ Design

- **3 Availability Zones**: Resources spread across 3 AZs
- **NAT Gateway per AZ**: No single point of failure
- **EKS Node Distribution**: Nodes distributed across AZs
- **S3 Replication**: Automatic cross-AZ replication

### Fault Tolerance

- **Node Group Auto-Scaling**: Automatic replacement of failed nodes
- **EKS Control Plane**: Managed by AWS across multiple AZs
- **S3 Durability**: 99.999999999% (11 9's) durability
- **ECR Availability**: 99.9% SLA

## Monitoring and Logging

### EKS Cluster Logs

Enabled log types:
- API server logs
- Audit logs
- Authenticator logs
- Controller manager logs
- Scheduler logs

### CloudWatch Integration

- Container Insights for pod metrics
- Log aggregation from all pods
- Custom metrics from ETL workloads

## Cost Breakdown

### Fixed Costs (Monthly)

| Resource | Cost |
|----------|------|
| EKS Control Plane | $73 |
| NAT Gateways (3) | $100 |
| **Subtotal** | **$173** |

### Variable Costs (Monthly)

| Resource | Configuration | Cost |
|----------|--------------|------|
| Spark Workers | 2x r6i.2xlarge | $730 |
| Polars Workers | 0-2x r6i.8xlarge | $0-$2,920 |
| S3 Storage | Per GB | ~$0.023/GB |
| S3 Requests | Per 1000 | ~$0.005 |
| Data Transfer | Per GB | ~$0.09/GB |

### Total Monthly Cost Estimate

- **Baseline (Spark only)**: ~$900/month
- **With Polars workers**: ~$3,800/month
- **Development (scaled to 0)**: ~$173/month

## Scaling Considerations

### Horizontal Scaling

**Spark Workers:**
- Can scale from 2 to 10 nodes
- Each node: 8 vCPU, 64GB RAM
- Total capacity: 16-80 vCPU, 128-640GB RAM

**Polars Workers:**
- Can scale from 0 to 2 nodes
- Each node: 32 vCPU, 256GB RAM
- Total capacity: 0-64 vCPU, 0-512GB RAM

### Vertical Scaling

To change instance types, update `terraform.tfvars`:

```hcl
spark_workers_config = {
  instance_type = "r6i.4xlarge"  # 16 vCPU, 128GB RAM
  # ...
}
```

## Maintenance

### Regular Tasks

1. **Update Kubernetes Version**: Every 3-6 months
2. **Rotate IAM Credentials**: Automatic with IRSA
3. **Review S3 Lifecycle**: Monthly
4. **Clean ECR Images**: Automatic via lifecycle policy
5. **Review CloudWatch Logs**: Weekly

### Terraform State

- State stored locally by default
- Consider using S3 backend for team collaboration
- Enable state locking with DynamoDB

## Disaster Recovery

### Backup Strategy

1. **S3 Versioning**: Enabled for data recovery
2. **Terraform State**: Backup before major changes
3. **EKS Configuration**: Stored in Git
4. **ECR Images**: Tagged and versioned

### Recovery Procedures

1. **Lost S3 Data**: Restore from versioned objects
2. **Cluster Failure**: Recreate with `terraform apply`
3. **Node Failure**: Automatic replacement by EKS
4. **Region Failure**: Deploy to different region

## Compliance

### AWS Best Practices

- ✅ Multi-AZ deployment
- ✅ Private subnets for compute
- ✅ Encryption at rest and in transit
- ✅ IAM roles instead of access keys
- ✅ CloudWatch logging enabled
- ✅ Security group restrictions
- ✅ Resource tagging

### Security Standards

- ✅ CIS AWS Foundations Benchmark
- ✅ AWS Well-Architected Framework
- ✅ Principle of least privilege
- ✅ Defense in depth

## Future Enhancements

### Potential Improvements

1. **Spot Instances**: 60-90% cost savings
2. **Cluster Autoscaler**: Automatic node scaling
3. **Karpenter**: Advanced node provisioning
4. **VPC Endpoints**: Reduce NAT gateway costs
5. **S3 Glacier**: Archive old benchmark data
6. **Multi-Region**: Disaster recovery setup
7. **Service Mesh**: Istio or App Mesh
8. **GitOps**: ArgoCD or Flux

## References

- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/)
- [S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/best-practices.html)
