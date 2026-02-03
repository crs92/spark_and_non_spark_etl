# Configuration Complexity Analysis: Spark vs Polars

This document tracks the configuration complexity and resource requirements discovered during the benchmark setup.

## Summary

**Key Finding**: Spark on EKS requires significantly more configuration complexity and infrastructure planning compared to Polars on AWS Batch.

---

## Configuration Complexity Comparison

### Spark on EKS

#### Infrastructure Requirements
- **Kubernetes Cluster**: EKS cluster with control plane
- **Node Groups**: Pre-provisioned worker nodes
- **Spark Operator**: Custom Kubernetes operator installation
- **Service Accounts**: IAM roles with Pod Identity
- **Network Configuration**: VPC, subnets, security groups
- **Resource Planning**: Must size nodes to fit executor + driver pods

#### Configuration Files Required
1. Terraform modules (VPC, EKS, IAM, node groups)
2. Spark Operator Helm chart
3. SparkApplication CRD manifests
4. Service account configurations
5. RBAC policies
6. Pod Identity associations

#### Resource Sizing Challenges

**Problem**: Spark requires careful resource planning to avoid pod scheduling failures.

**Example from our setup**:
- Initial attempt: t3.small nodes (2 vCPU, 8GB)
- Spark SF=10 requirements: 1 driver + 4 executors = 5 cores + 20GB
- **Result**: Executors stuck in Pending state - insufficient resources

**Iterations required**:
1. First attempt: Default configuration failed
2. Second attempt: Reduced to 2 executors, still tight fit
3. Third attempt: Upgraded nodes to m6i.xlarge (4 vCPU, 16GB)
4. Fourth attempt: Adjusted executor count and memory per scale factor

**Configuration complexity score**: 8/10

---

### Polars on AWS Batch

#### Infrastructure Requirements
- **AWS Batch**: Managed service, no cluster management
- **Fargate**: Serverless compute, no node provisioning
- **IAM Role**: Single role for task execution
- **Job Definition**: Simple JSON configuration

#### Configuration Files Required
1. Terraform for Batch (job queue, job definition, IAM role)
2. Docker image with application code

#### Resource Sizing

**Advantage**: Resources specified per job, no cluster capacity planning needed.

**Example from our setup**:
```python
# Simple resource specification
vcpu = 4
memory_gb = 16
```

**Iterations required**: 1 (worked on first try after fixing credentials)

**Configuration complexity score**: 3/10

---

## Resource Requirements Tracking

### Scale Factor 1 (SF=1, ~1GB data)

| Component | Spark (EKS) | Polars (Batch) |
|-----------|-------------|----------------|
| Driver/Main | 1 core, 2GB | - |
| Executors/Workers | 2 × (1 core, 2GB) | 4 vCPU, 8GB |
| **Total** | **3 cores, 6GB** | **4 vCPU, 8GB** |
| Cluster overhead | EKS control plane + system pods (~1GB) | None (serverless) |
| **Actual infrastructure** | 2 × t3.small (4 vCPU, 16GB) | On-demand Fargate |

### Scale Factor 10 (SF=10, ~10GB data)

| Component | Spark (EKS) | Polars (Batch) |
|-----------|-------------|----------------|
| Driver/Main | 1 core, 2GB | - |
| Executors/Workers | 2 × (1 core, 3GB) | 4 vCPU, 8GB |
| **Total** | **3 cores, 8GB** | **4 vCPU, 8GB** |
| Cluster overhead | EKS control plane + system pods | None |
| **Actual infrastructure** | 2 × t3.small (4 vCPU, 16GB) | On-demand Fargate |

**Note**: With t3.small nodes, we had to reduce Spark resources significantly. For fair comparison, we should use m6i.xlarge nodes.

### Scale Factor 10 (SF=10) - Fair Comparison with m6i.xlarge

| Component | Spark (EKS) | Polars (Batch) |
|-----------|-------------|----------------|
| Driver/Main | 1 core, 4GB | - |
| Executors/Workers | 4 × (1 core, 4GB) | 4 vCPU, 16GB |
| **Total** | **5 cores, 20GB** | **4 vCPU, 16GB** |
| Cluster overhead | EKS control plane + system pods | None |
| **Actual infrastructure** | 3 × m6i.xlarge (12 vCPU, 48GB) | On-demand Fargate |

### Scale Factor 100 (SF=100, ~100GB data)

| Component | Spark (EKS) | Polars (Batch) |
|-----------|-------------|----------------|
| Driver/Main | 1 core, 4GB | - |
| Executors/Workers | 4 × (1 core, 4GB) | 8 vCPU, 16GB |
| **Total** | **5 cores, 20GB** | **8 vCPU, 16GB** |
| Cluster overhead | EKS control plane + system pods | None |
| **Actual infrastructure** | 3 × m6i.xlarge (12 vCPU, 48GB) | On-demand Fargate |

---

## Configuration Issues Encountered

### Spark on EKS

1. **Pod Scheduling Failures**
   - Issue: Executors stuck in Pending state
   - Cause: Insufficient node resources
   - Resolution: Multiple iterations of resource tuning
   - Time to resolve: ~2 hours

2. **Resource Fragmentation**
   - Issue: Can't fully utilize node capacity
   - Example: m6i.xlarge has 4 vCPU, but Spark uses 5 cores (driver + 4 executors)
   - Result: Need 3 nodes but only use ~60% of total capacity

3. **Startup Latency**
   - Issue: Pods must be scheduled, images pulled, containers started
   - Observed: 30-60 seconds before job starts executing

4. **Configuration Drift**
   - Issue: Terraform state on different machine had different instance types
   - Resolution: Manual state management or re-import

### Polars on AWS Batch

1. **DuckDB S3 Credentials**
   - Issue: DuckDB couldn't access S3 with IAM role
   - Cause: Missing boto3 credential fetching
   - Resolution: Added boto3 session credential fetch
   - Time to resolve: ~30 minutes

2. **Job Definition Missing**
   - Issue: Terraform not applied from original machine
   - Resolution: Apply Terraform with data sources for existing resources
   - Time to resolve: ~15 minutes

---

## Operational Complexity

### Spark on EKS

**Pre-flight checklist**:
- [ ] EKS cluster running
- [ ] Nodes have sufficient capacity
- [ ] Spark Operator installed
- [ ] Service accounts configured
- [ ] IAM roles attached
- [ ] kubectl configured
- [ ] ECR images pushed
- [ ] Resource requests fit in node capacity

**Ongoing maintenance**:
- Monitor node utilization
- Scale node groups as needed
- Update Spark Operator
- Manage Kubernetes versions
- Handle pod evictions
- Debug scheduling issues

### Polars on AWS Batch

**Pre-flight checklist**:
- [ ] Job definition exists
- [ ] Job queue active
- [ ] IAM role has S3 permissions
- [ ] ECR image pushed

**Ongoing maintenance**:
- Update job definition if needed
- Monitor job failures

---

## Cost Implications of Configuration Complexity

### Spark on EKS

**Fixed costs** (even when idle):
- EKS control plane: $0.10/hour = $73/month
- Minimum 2 nodes running 24/7: ~$60-240/month depending on instance type

**Variable costs**:
- Additional nodes during job execution
- Data transfer
- EBS volumes

**Wasted capacity**:
- Nodes must be sized for peak load
- Idle capacity between jobs
- Resource fragmentation (can't use 100% of node capacity)

### Polars on AWS Batch

**Fixed costs**: $0 (serverless)

**Variable costs**:
- Pay only for job execution time
- No idle capacity costs
- No wasted resources

---

## Recommendations

### For Small-Scale Workloads (SF=1, SF=10)
**Winner**: Polars on AWS Batch
- Lower configuration complexity
- No cluster management
- Pay-per-use pricing
- Faster to set up and iterate

### For Large-Scale Workloads (SF=100+)
**Consider**: Both options, but factor in:
- Spark: Better for distributed processing across many nodes
- Polars: Better for single-node optimization, but may hit Fargate limits (16 vCPU, 120GB max)

### For Production Workloads
**Key considerations**:
1. **Team expertise**: Does team know Kubernetes?
2. **Workload patterns**: Continuous vs. batch?
3. **Cost sensitivity**: Fixed vs. variable costs?
4. **Operational overhead**: Who manages the infrastructure?

---

## Conclusion

**Configuration complexity is a significant factor** in choosing between Spark and Polars:

- **Spark on EKS**: High complexity, requires Kubernetes expertise, careful resource planning
- **Polars on AWS Batch**: Low complexity, serverless, simple resource specification

**This complexity difference should be factored into TCO analysis**, not just compute costs.

**Estimated setup time**:
- Spark on EKS: 4-8 hours (first time), 1-2 hours (subsequent)
- Polars on Batch: 1-2 hours (first time), 15 minutes (subsequent)

**Estimated operational overhead**:
- Spark on EKS: 2-4 hours/week (monitoring, scaling, updates)
- Polars on Batch: <1 hour/week (mostly monitoring)
