# Requirements Document

## Introduction

This PoC demonstrates a strategic comparison between **Vertical Scaling** (single-node processing with Polars on EC2) and **Horizontal Scaling** (distributed processing with Spark on EKS). The goal is to identify the **crossover point** where distributed processing becomes necessary, answering the critical question: "When do you actually need Spark?"

The benchmark uses the **NYC Taxi Trip dataset** (publicly available on S3) to provide realistic, production-grade data at multiple scales. By comparing a simple EC2 instance running Polars against a full EKS cluster running Spark, we demonstrate:

1. **Performance characteristics** across data sizes (1GB to 100GB+)
2. **Infrastructure complexity** (single VM vs. Kubernetes cluster)
3. **Total Cost of Ownership** (compute + operational overhead)
4. **Operational simplicity** (deployment, monitoring, debugging)

This is not about proving one technology is "better" - it's about showing **when each approach is optimal** for different workload characteristics.

## Glossary

- **Vertical Scaling**: Increasing resources (CPU, RAM) on a single machine
- **Horizontal Scaling**: Adding more machines to distribute workload
- **Crossover Point**: Data size where distributed processing becomes cost-effective
- **TCO**: Total Cost of Ownership (compute + operational overhead)
- **NYC TLC**: NYC Taxi and Limousine Commission (data provider)
- **Data Localization**: Copying data to the same AWS region as compute resources to eliminate cross-region transfer costs and latency
- **Cross-Region Transfer**: Data movement between AWS regions that incurs network costs and latency

## Requirements

### Requirement 1

**User Story:** As a data engineer, I want to identify the crossover point where distributed processing becomes necessary, so that I can avoid over-engineering simple ETL workloads.

#### Acceptance Criteria

1. WHEN the benchmark runs THEN the system SHALL execute identical ETL logic on both EC2 (Polars) and EKS (Spark)
2. WHEN processing different data volumes (1GB, 10GB, 50GB, 100GB) THEN the system SHALL measure execution time, memory usage, and infrastructure cost for each approach
3. WHEN benchmarks complete THEN the system SHALL identify the data size where Spark becomes faster than Polars
4. WHEN analyzing results THEN the system SHALL calculate the crossover point considering both performance and cost

### Requirement 2

**User Story:** As a DevOps engineer, I want to compare infrastructure complexity between single-node and distributed deployments, so that I can understand the operational overhead of each approach.

#### Acceptance Criteria

1. WHEN deploying Polars THEN the system SHALL use a single EC2 instance with no orchestration overhead
2. WHEN deploying Spark THEN the system SHALL use EKS with Spark Operator for native Kubernetes integration
3. WHEN measuring complexity THEN the system SHALL track deployment time, configuration steps, and monitoring requirements
4. WHEN comparing approaches THEN the system SHALL document the operational differences (VM vs. K8s cluster management)

### Requirement 3

**User Story:** As a technical writer, I want clear "Ant vs. Cannon" narratives with cost analysis, so that I can create compelling content about when to use each approach.

#### Acceptance Criteria

1. WHEN benchmarks complete THEN the system SHALL generate reports with the "Vertical vs. Horizontal Scaling" narrative
2. WHEN presenting results THEN the system SHALL show cost-per-GB and cost-per-hour metrics for both approaches
3. WHEN documenting findings THEN the system SHALL provide decision framework: "Use Polars when X, use Spark when Y"
4. WHEN analyzing crossover point THEN the system SHALL explain why distributed processing becomes necessary at that scale

### Requirement 4

**User Story:** As a data platform architect, I want to use real-world production data (NYC Taxi) instead of synthetic data, so that benchmark results reflect actual workload characteristics.

#### Acceptance Criteria

1. WHEN accessing data THEN the system SHALL read from a localized S3 bucket in eu-central-1 containing NYC Taxi data
2. WHEN processing data THEN the system SHALL perform realistic ETL operations: filter invalid trips, calculate metrics, aggregate by location
3. WHEN scaling tests THEN the system SHALL use actual data sizes: 1 month (~1GB), 1 year (~10GB), 5 years (~50GB), 10 years (~100GB)
4. WHEN measuring performance THEN the system SHALL track end-to-end time including S3 read, processing, and write operations

### Requirement 5

**User Story:** As a developer, I want simple configuration for different data sizes and instance types, so that I can easily run benchmarks across the scaling spectrum.

#### Acceptance Criteria

1. WHEN configuring EC2 THEN the system SHALL support instance types: r6i.2xlarge (8 vCPU, 64GB), r6i.4xlarge (16 vCPU, 128GB)
2. WHEN configuring Spark THEN the system SHALL support executor scaling: 2, 5, 10, 20 executors
3. WHEN selecting data THEN the system SHALL support time ranges: 1 month, 1 year, 5 years, 10 years
4. WHEN running tests THEN the system SHALL use consistent ETL logic across both implementations

### Requirement 6

**User Story:** As a cloud architect, I want to deploy Polars on EC2 and Spark on EKS to compare infrastructure approaches, so that I can demonstrate the complexity difference.

#### Acceptance Criteria

1. WHEN deploying Polars THEN the system SHALL launch a single EC2 instance with Python, Polars, and s3fs installed
2. WHEN deploying Spark THEN the system SHALL use EKS with Spark Operator and Pod Identity Association for S3 access
3. WHEN accessing S3 THEN the system SHALL read directly from public NYC Taxi bucket (no data upload needed)
4. WHEN writing results THEN the system SHALL use the benchmark's own S3 bucket with appropriate permissions
5. WHEN monitoring THEN the system SHALL track EC2 instance metrics and EKS pod metrics separately

### Requirement 7

**User Story:** As a cost-conscious engineer, I want detailed cost analysis showing TCO for each approach, so that I can make economically informed technology decisions.

#### Acceptance Criteria

1. WHEN calculating EC2 costs THEN the system SHALL include instance hourly rate × execution time
2. WHEN calculating EKS costs THEN the system SHALL include control plane ($0.10/hr) + node costs + execution time
3. WHEN comparing costs THEN the system SHALL show cost-per-GB-processed for both approaches
4. WHEN analyzing TCO THEN the system SHALL include operational overhead: deployment complexity, monitoring setup, debugging time
5. WHEN using Graviton instances THEN the system SHALL demonstrate 20% cost savings vs x86 instances

### Requirement 8

**User Story:** As a security engineer, I want to use EKS Pod Identity Association instead of IRSA for S3 access, so that I can simplify IAM configuration and improve security.

#### Acceptance Criteria

1. WHEN configuring S3 access THEN the system SHALL use EKS Pod Identity Association instead of IRSA (IAM Roles for Service Accounts)
2. WHEN creating IAM roles THEN the system SHALL associate them directly with EKS pods using Pod Identity
3. WHEN Spark pods access S3 THEN the system SHALL automatically assume the correct IAM role without manual ServiceAccount annotations
4. WHEN documenting setup THEN the system SHALL explain the benefits of Pod Identity over IRSA (simpler configuration, better security)

### Requirement 9

**User Story:** As a performance engineer, I want to localize NYC Taxi data to eu-central-1 before running benchmarks, so that I measure compute performance rather than network latency and avoid cross-region transfer costs.

#### Acceptance Criteria

1. WHEN the source data is in us-east-1 and compute resources are in eu-central-1 THEN the system SHALL copy data to a local S3 bucket before benchmarking
2. WHEN copying data THEN the system SHALL use EC2 instance with high network bandwidth to perform S3-to-S3 transfer within AWS backbone
3. WHEN selecting data subsets THEN the system SHALL copy specific time ranges: 1 month for small tests, 1 year for medium tests, 5 years for large tests
4. WHEN data localization is complete THEN the system SHALL update configuration to read from the eu-central-1 bucket
5. WHEN benchmarks run THEN the system SHALL read data from the same region as compute resources to ensure consistent performance measurements
