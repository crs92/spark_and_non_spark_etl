# Implementation Plan: Vertical vs. Horizontal Scaling Benchmark

## Overview

This implementation plan focuses on comparing **single-node Polars (EC2)** against **distributed Spark (EKS)** using the real-world NYC Taxi dataset. The goal is to identify the crossover point where distributed processing becomes necessary.

**Key Strategy Changes:**
- ✅ Use NYC Taxi public S3 data (no data generation needed)
- ✅ Deploy Polars on EC2 (vertical scaling)
- ✅ Deploy Spark on EKS (horizontal scaling)
- ✅ Use Pod Identity Association instead of IRSA
- ✅ Focus on cost analysis and TCO

---

## Phase 0: Data Localization (NYC Taxi to eu-central-1)

- [ ] 0. Localize NYC Taxi data to eu-central-1 for stable benchmarks
  - Copy data from us-east-1 to local S3 bucket
  - Update configuration to use local bucket
  - Verify data integrity after copy
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 0.1 Create data localization script
  - Write `scripts/localize_nyc_taxi_data.sh`
  - Detect source and target regions
  - Use EC2 instance for S3-to-S3 copy
  - Support small, medium, large dataset sizes
  - Add progress tracking and error handling
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 0.2 Copy small dataset (1 month, ~40MB)
  - Copy yellow_tripdata_2022-01.parquet to local bucket
  - Verify file size and record count
  - Update configuration to point to local path
  - _Requirements: 9.1, 9.3, 9.4_

- [x] 0.3 Copy medium dataset (1 year, ~1.2GB)
  - Copy all 2022 files to local bucket
  - Verify file count (12 files)
  - Update configuration for medium tests
  - _Requirements: 9.1, 9.3, 9.4_

- [x] 0.4 Copy large dataset (5 years, ~10GB)
  - Copy 2018-2022 files to local bucket
  - Verify file count (60 files)
  - Update configuration for large tests
  - _Requirements: 9.1, 9.3, 9.4_

- [ ] 0.5 Write property test for cross-region detection
  - **Property 1: Cross-region detection triggers localization**
  - **Validates: Requirements 9.1**
  - Generate random region pairs
  - Verify localization triggers when regions differ
  - Use Hypothesis with 100 iterations
  - _Requirements: 9.1_

- [ ] 0.6 Write property test for dataset size mapping
  - **Property 2: Dataset size maps to correct time range**
  - **Validates: Requirements 9.3**
  - Generate random dataset size requests
  - Verify correct time range selection (small→1mo, medium→1yr, large→5yr)
  - Use Hypothesis with 100 iterations
  - _Requirements: 9.3_

- [ ] 0.7 Write property test for configuration updates
  - **Property 3: Configuration updates after localization**
  - **Validates: Requirements 9.4**
  - Generate random localization scenarios
  - Verify configuration points to local bucket after completion
  - Use Hypothesis with 100 iterations
  - _Requirements: 9.4_

- [ ] 0.8 Write property test for region consistency
  - **Property 4: Region consistency during benchmarks**
  - **Validates: Requirements 9.5**
  - Generate random benchmark configurations
  - Verify data source region matches compute region
  - Use Hypothesis with 100 iterations
  - _Requirements: 9.5_

- [x] 0.9 Update NYC Taxi config to use localized data
  - Modify `src/etl/nyc_taxi_config.py`
  - Add region detection logic
  - Update S3 paths to use local bucket
  - Add fallback to public bucket if local not available
  - _Requirements: 9.4, 9.5_

---

## Phase 1: NYC Taxi ETL Implementation

- [x] 1. Implement NYC Taxi ETL logic for both stacks
  - Create shared ETL logic that both implementations will use
  - Define data size configurations (tiny, small, medium, large, xlarge)
  - Implement identical transformation logic
  - _Requirements: 1.1, 4.1, 4.2_

- [x] 1.1 Create NYC Taxi data access module
  - Write Python module to read from `s3://nyc-tlc/trip data/`
  - Support date range selection (1 month to 10 years)
  - Handle schema evolution across years
  - Add data validation and error handling
  - _Requirements: 4.1, 4.2_

- [x] 1.2 Implement Polars NYC Taxi ETL
  - Create `src/etl/polars_etl_nyc_taxi.py`
  - Implement Extract: Read Parquet from S3 using s3fs
  - Implement Transform: Filter, calculate price_per_mile, aggregate by location
  - Implement Load: Write results to benchmark S3 bucket
  - Add timing and memory tracking
  - _Requirements: 1.1, 1.2, 4.2, 4.4_

- [x] 1.3 Implement Spark NYC Taxi ETL
  - Create `src/etl/spark_etl_nyc_taxi.py`
  - Implement identical ETL logic using PySpark
  - Use s3a:// protocol for S3 access
  - Add timing and resource tracking
  - Ensure output matches Polars implementation exactly
  - _Requirements: 1.1, 1.2, 4.2, 4.4_

- [ ]* 1.4 Write integration tests for ETL equivalence
  - Test that both implementations produce identical results
  - Validate data quality checks
  - Test error handling
  - _Requirements: 1.1, 1.2_

---

## Phase 2: EC2 Deployment for Polars (Vertical Scaling)

- [x] 2. Deploy Polars on EC2 for vertical scaling comparison
  - Set up single EC2 instance with Polars
  - Configure S3 access via IAM instance profile
  - Create deployment automation
  - _Requirements: 2.1, 2.2, 6.1, 6.2_

- [x] 2.1 Create EC2 Terraform module
  - Write `terraform/modules/ec2/main.tf`
  - Configure instance types: r6i.2xlarge, r6i.4xlarge, r7g.2xlarge (Graviton)
  - Create IAM instance profile with S3 read/write permissions
  - Add security group for SSH access
  - Configure CloudWatch agent for monitoring
  - _Requirements: 2.1, 6.1, 6.2_

- [x] 2.2 Create EC2 user data script for Polars setup
  - Write `scripts/ec2_setup_polars.sh`
  - Install Python 3.12, uv, Polars, s3fs, boto3
  - Clone ETL repository
  - Configure CloudWatch agent
  - Set up systemd service for ETL execution
  - _Requirements: 2.1, 6.1_

- [x] 2.3 Create EC2 deployment script
  - Write `scripts/deploy_ec2_polars.sh`
  - Launch EC2 instance with Terraform
  - Wait for instance to be ready
  - Verify Polars installation
  - Test S3 access
  - _Requirements: 2.1, 2.2, 6.1_

- [x] 2.4 Create EC2 benchmark execution script
  - Write `scripts/run_ec2_benchmark.sh`
  - SSH to EC2 instance
  - Execute Polars ETL with specified data size
  - Collect metrics (execution time, memory usage)
  - Download results from S3
  - _Requirements: 1.2, 2.1, 5.1_

---

## Phase 3: EKS Deployment for Spark (Horizontal Scaling)

- [x] 3. Deploy EKS infrastructure with Terraform
  - ✅ **COMPLETED**: EKS cluster, VPC, S3, ECR, IAM modules created
  - ✅ **Created**: Terraform modules for all AWS resources
  - _Requirements: 2.3, 6.1, 6.2_

- [x] 4. Install Spark Operator on EKS
  - ✅ **COMPLETED**: Spark Operator v1.4.8 installed via Helm
  - ✅ **Created**: Installation, configuration, and verification scripts
  - ✅ **Created**: SparkApplication manifest template
  - _Requirements: 2.2, 2.3, 6.2_

- [x] 5. Configure Pod Identity Association for Spark
  - Replace IRSA with EKS Pod Identity Association
  - Update Terraform IAM module
  - Update SparkApplication manifest
  - Test S3 access from Spark pods
  - _Requirements: 6.2, 6.3, 8.1, 8.2, 8.3_

- [x] 5.1 Update Terraform for Pod Identity
  - Add `aws_eks_pod_identity_association` resource
  - Remove OIDC provider configuration
  - Simplify IAM role trust policy
  - Update ServiceAccount configuration
  - _Requirements: 6.2, 8.1, 8.2_

- [x] 5.2 Update SparkApplication for Pod Identity
  - Remove IRSA annotations from ServiceAccount
  - Update Spark configuration for Pod Identity
  - Test S3 access with new authentication method
  - Document benefits over IRSA
  - _Requirements: 6.2, 8.1, 8.3_

- [x] 6. Build and push AMD Docker images to ECR
  - Update Dockerfiles for NYC Taxi ETL
  - Add S3 access libraries
  - Push to ECR
  - _Requirements: 2.1, 2.3_

- [x] 6.1 Update Dockerfile.spark for NYC Taxi ETL
  - Add AWS Hadoop libraries for S3 access
  - Copy NYC Taxi ETL script
  - Add required Python dependencies
  - Test local build
  - _Requirements: 2.1, 2.3_

- [x] 6.2 Update Dockerfile.polars for NYC Taxi ETL (if using EKS)
  - Add boto3 and s3fs for S3 access
  - Copy NYC Taxi ETL script
  - Add required Python dependencies
  - Test local build
  - _Requirements: 2.1, 2.3_

- [x] 6.3 Push images to ECR
  - Authenticate with ECR
  - Tag images with version
  - Push spark-etl image
  - Push polars-etl image (if needed)
  - Add Makefile targets
  - _Requirements: 2.1, 2.3_

- [x] 7. Create SparkApplication manifests for different scales
  - Create manifests for tiny, small, medium, large, xlarge datasets
  - Configure executor scaling for each size
  - Add cost tracking labels
  - _Requirements: 1.1, 2.2, 5.1, 5.2_

- [x] 7.1 Create SparkApplication for tiny dataset (1 month)
  - 2 executors, 4 cores, 8GB each
  - Read from s3://nyc-tlc/trip data/yellow_tripdata_2022-01.parquet
  - Write to benchmark bucket
  - _Requirements: 1.1, 5.1_

- [x] 7.2 Create SparkApplication for small dataset (1 year)
  - 3 executors, 4 cores, 8GB each
  - Read 12 months of data
  - _Requirements: 1.1, 5.1_

- [x] 7.3 Create SparkApplication for medium dataset (3 years)
  - 5 executors, 4 cores, 16GB each
  - Read 36 months of data
  - _Requirements: 1.1, 5.1_

- [x] 7.4 Create SparkApplication for large dataset (5 years)
  - 10 executors, 4 cores, 16GB each
  - Read 60 months of data
  - _Requirements: 1.1, 5.1_

- [x] 7.5 Create SparkApplication for xlarge dataset (8+ years)
  - 20 executors, 4 cores, 16GB each
  - Read 96+ months of data
  - _Requirements: 1.1, 5.1_

---

## Phase 4: Benchmark Execution and Metrics Collection

- [x] 8. Create benchmark orchestration framework
  - Automate execution of both EC2 and EKS benchmarks
  - Collect metrics from both environments
  - Store results in S3
  - _Requirements: 1.2, 3.1, 3.2, 5.1_

- [x] 8.1 Create benchmark orchestration script
  - Write `scripts/run_full_benchmark.py`
  - Execute EC2 benchmarks for all data sizes
  - Execute EKS benchmarks for all data sizes
  - Collect metrics from CloudWatch
  - Download results from S3
  - _Requirements: 1.2, 5.1_

- [x] 8.2 Implement CloudWatch metrics collection
  - Query EC2 instance metrics (CPU, memory, network)
  - Query EKS pod metrics (CPU, memory, network)
  - Calculate execution time from logs
  - Export metrics to JSON
  - _Requirements: 1.2, 4.4, 6.5_

- [x] 8.3 Create results validation script
  - Verify both implementations produce identical results
  - Check data quality
  - Validate record counts
  - Compare aggregation results
  - _Requirements: 1.1, 1.3_

---

## Phase 5: Cost Analysis and Reporting

- [x] 9. Implement comprehensive cost analysis
  - Calculate EC2 costs (instance hours + S3)
  - Calculate EKS costs (control plane + nodes + S3)
  - Compare cost-per-GB-processed
  - Include operational overhead in TCO
  - _Requirements: 3.1, 3.2, 7.1, 7.2, 7.3, 7.4_

- [x] 9.1 Create cost calculation module
  - Write `src/analysis/cost_calculator.py`
  - Implement EC2 cost model
  - Implement EKS cost model
  - Calculate cost-per-GB and cost-per-hour
  - Add Graviton cost comparison
  - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 9.2 Create TCO analysis module
  - Write `src/analysis/tco_analyzer.py`
  - Include deployment time costs
  - Include monitoring setup costs
  - Include debugging complexity costs
  - Calculate total operational overhead
  - _Requirements: 7.4_

- [x] 9.3 Identify crossover point
  - Analyze performance vs. data size
  - Find where Spark becomes faster
  - Find where Spark becomes cost-effective
  - Document the crossover point
  - _Requirements: 1.3, 1.4, 3.2_

- [x] 10. Create comprehensive benchmark report
  - Generate "Vertical vs. Horizontal Scaling" report
  - Include performance charts
  - Include cost analysis
  - Include decision framework
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 10.1 Create report generator
  - Write `scripts/generate_benchmark_report.py`
  - Generate performance comparison charts
  - Generate cost comparison charts
  - Create crossover point visualization
  - Export to Markdown and PowerPoint
  - _Requirements: 3.1, 3.2_

- [x] 10.2 Create decision framework document
  - Write `docs/DECISION_FRAMEWORK.md`
  - Define "Use Polars when..." criteria
  - Define "Use Spark when..." criteria
  - Include cost considerations
  - Include operational complexity considerations
  - _Requirements: 3.2, 3.3_

---

## Phase 6: Documentation and Cleanup

- [x] 11. Create comprehensive documentation
  - Update README with new strategy
  - Create deployment guides
  - Document cost analysis methodology
  - _Requirements: 3.3_

- [x] 11.1 Update README with "Ant vs. Cannon" narrative
  - Explain vertical vs. horizontal scaling
  - Show example results
  - Include cost comparison
  - Add decision framework summary
  - _Requirements: 3.3_

- [x] 11.2 Create EC2 deployment guide
  - Write `docs/EC2_DEPLOYMENT.md`
  - Step-by-step EC2 setup
  - Polars installation
  - Benchmark execution
  - Troubleshooting
  - _Requirements: 2.4, 3.3_

- [x] 11.3 Create EKS deployment guide
  - Write `docs/EKS_DEPLOYMENT.md`
  - Step-by-step EKS setup
  - Spark Operator installation
  - Pod Identity configuration
  - Benchmark execution
  - _Requirements: 2.3, 3.3_

- [x] 11.4 Create cost analysis guide
  - Write `docs/COST_ANALYSIS.md`
  - Explain cost calculation methodology
  - Show example cost breakdowns
  - Include TCO considerations
  - Provide cost optimization tips
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 12. Add Makefile targets for new workflow
  - Add EC2 deployment targets
  - Add benchmark execution targets
  - Add cost analysis targets
  - Add cleanup targets
  - _Requirements: 5.1, 5.2_

---

## Summary of Changes from Original Plan

**Removed Tasks:**
- ❌ Task 1: Generate synthetic clickstream data (using NYC Taxi instead)
- ❌ Task 14: Generate benchmark datasets on EKS (using public data)

**Added Tasks:**
- ✅ Phase 1: NYC Taxi ETL implementation
- ✅ Phase 2: EC2 deployment for Polars
- ✅ Phase 5: Comprehensive cost analysis and TCO

**Updated Tasks:**
- 🔄 Task 11: Use Pod Identity instead of IRSA
- 🔄 Task 13: Read from NYC Taxi public bucket
- 🔄 Task 15: Focus on cost analysis and crossover point

**Preserved Tasks:**
- ✅ Phase 3: EKS and Spark Operator (already completed)
- ✅ Docker builds and ECR push
- ✅ Monitoring and metrics collection
