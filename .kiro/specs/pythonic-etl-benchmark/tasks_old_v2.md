# Implementation Plan

- [x] 1. Generate realistic clickstream data with configurable sizes for benchmark testing using Faker
  - ✅ **COMPLETED**: Implemented simplified clickstream data generator focused on ETL benchmarking
  - ✅ **Created**: `src/data_generation/` module with `ClickstreamDataGenerator` class
  - ✅ **Features**:
    - Configurable data sizes: Small (100K), Medium (10M), Large (100M) records
    - Support for CSV and Parquet formats
    - Bulk load files (30 days historical data) + incremental daily files
    - Timestamp-based data organization for realistic ETL scenarios
    - Reproducible generation with seed support
    - Realistic clickstream schema: event_id, user_id, session_id, timestamp, page_url, country, device, ip_address
  - ✅ **CLI Tool**: Created `generate_data.py` for easy command-line usage
    - Usage: `python generate_data.py small|medium|large [options]`
    - Options: --output, --formats, --days, --seed, --quiet
  - ✅ **Documentation**: Added comprehensive README with usage examples
  - ✅ **Output Structure**:
    ```
    data/
    ├── bulk/                    # Historical data for initial load
    │   ├── bulk_data_small.csv
    │   └── bulk_data_small.parquet
    └── incremental/             # Daily files for incremental processing
        ├── incremental_2024-02-01_small.csv
        └── incremental_2024-02-01_small.parquet
    ```
  - ✅ **Testing**: All 19 tests passing, including reproducibility and scalability tests
  - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2_

- [x] 2. Implement proper sessionization logic in both ETL stacks
  - ✅ **COMPLETED**: Implemented 30-minute inactivity window sessionization
  - ✅ **Spark Implementation**: Window functions with lag() and cumulative sum for session boundaries
  - ✅ **Polars Implementation**: Equivalent logic using shift() and cum_sum() over user partitions
  - ✅ **Session Metrics**: Added session_start, session_end, and session_duration_minutes
  - ✅ **Testing**: Created comprehensive sessionization tests validating both implementations
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 3. Implement comprehensive data cleansing and type casting





  - Add null value handling and data validation logic
  - Implement consistent type casting across both ETL implementations
  - Add data quality checks and error handling
  - Ensure identical data transformation logic between stacks
  - ✅ **COMPLETED**: Implemented shared data quality module
  - ✅ **Created**: `src/etl/data_quality.py` with DataQualityConfig and DataQualityReport
  - ✅ **Both Implementations**: Applied identical logic to Spark and Polars ETL
  - ✅ **Testing**: 14 integration tests verifying output equivalence
  - ✅ **Documentation**: Created data-quality-guide.md
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3_

- [x] 4. Create staged pipeline complexity benchmark framework






  - Build progressive complexity pipeline stages (baseline → full pipeline)
  - Implement 5 pipeline stages with incremental feature additions
  - Create benchmark runner that executes all stages and compares results
  - Add stage-specific metrics collection (I/O, transformation, aggregation overhead)
  - Generate comparative analysis showing performance crossover points
  - Write tests validating each pipeline stage produces correct output
  - _Requirements: 1.1, 1.2, 3.1, 3.2, 4.3, 5.1_

- [x] 5. Fix Docker builds and enable local container testing




- [x] 5.1 Fix Dockerfile.spark for podman compatibility


  - Update base image to work with podman
  - Ensure Java and Spark dependencies install correctly
  - Test build with `make docker-build-spark`
  - Verify container runs with sample data
  - _Requirements: 2.1, 2.2_

- [x] 5.2 Fix Dockerfile.pythonic for podman compatibility












  - Ensure Python dependencies install correctly
  - Test build with `make docker-build-pythonic`
  - Verify container runs with sample data
  - _Requirements: 2.1, 2.2_

- [x] 5.3 Fix docker-compose.yml for podman-compose




  - Remove problematic volume mounts
  - Test infrastructure services (minio, postgres)
  - Verify `make docker-up` works
  - Test end-to-end with `make docker-run-spark` and `make docker-run-pythonic`
  - _Requirements: 2.1, 2.2_

- [x] 6. Implement complete bulk + incremental ETL workflow locally





- [x] 6.1 Create bulk + incremental data generation


  - Generate bulk historical data (30 days)
  - Generate incremental daily files (7 days)
  - Organize data in proper directory structure
  - Add CLI command: `make generate-data-full`
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 6.2 Implement bulk load in Polars ETL


  - Load bulk historical data
  - Process and write to output
  - Track metrics (time, memory, records)
  - Test with: `python -m src.etl.polars_etl --mode bulk`
  - _Requirements: 1.1, 1.2, 4.2_

- [x] 6.3 Implement incremental processing in Polars ETL


  - Load incremental daily files
  - Merge with existing bulk data
  - Handle duplicates and updates
  - Test with: `python -m src.etl.polars_etl --mode incremental`
  - _Requirements: 1.1, 1.2, 4.2_

- [x] 6.4 Implement bulk load in Spark ETL


  - Load bulk historical data
  - Process and write to output
  - Track metrics (time, memory, records)
  - Test with: `python -m src.etl.spark_etl --mode bulk`
  - _Requirements: 1.1, 1.2, 4.2_

- [x] 6.5 Implement incremental processing in Spark ETL


  - Load incremental daily files
  - Merge with existing bulk data
  - Handle duplicates and updates
  - Test with: `python -m src.etl.spark_etl --mode incremental`
  - _Requirements: 1.1, 1.2, 4.2_

- [x] 6.6 Create complete ETL benchmark script




  - Run bulk + incremental for both frameworks
  - Compare performance metrics
  - Generate comparison report
  - Add command: `make benchmark-full`
  - _Requirements: 3.1, 3.2, 5.1_

- [ ] 7. Implement comprehensive resource monitoring system
- [ ] 7.1 Enhance existing Docker resource monitoring
  - Improve existing container metrics collection (CPU, memory, I/O) for accuracy
  - Add application-level metrics collection for processing throughput and query execution times
  - Implement more detailed disk I/O and network monitoring
  - Add error rate and performance regression detection
  - _Requirements: 1.2, 1.3, 2.1, 2.2, 4.4_

- [ ] 7.2 Add Kubernetes-specific monitoring capabilities
  - Implement Kubernetes-specific monitoring for pod resource usage and node utilization
  - Add cluster-level metrics collection and analysis
  - Create infrastructure metrics monitoring for storage I/O and network latency
  - Implement service response time monitoring across distributed components
  - Write unit tests for metrics collection accuracy and data integrity
  - _Requirements: 2.1, 2.2, 2.3, 4.4_

- [x] 8. Build Iceberg integration for both ETL stacks
  - ✅ **COMPLETED**: Implemented Apache Iceberg support for both Polars and Spark ETL
  - ✅ **Created**: `src/etl/iceberg_config.py` with local SQLite-based catalog
  - ✅ **Features**:
    - Local Iceberg warehouse at `data/iceberg_warehouse/`
    - Table: `etl.clickstream_events` with 11 fields
    - Primary key: event_id (required)
    - Bulk mode: Create/overwrite table
    - Incremental mode: Merge/upsert on primary key
    - ACID transactions with metadata versioning
  - ✅ **Polars Implementation**: PyIceberg with manual merge logic
  - ✅ **Spark Implementation**: Iceberg Spark Runtime with SQL MERGE
  - ✅ **Testing**: Verified with 106,146 records (bulk + incremental)
  - ✅ **Documentation**: Created comprehensive Iceberg implementation guide
  - ✅ **Verification Tool**: `scripts/verify_iceberg.py` for table inspection
  - _Requirements: 1.1, 2.3, 4.2_

- [x] 8.1 Implement PyIceberg integration in Pythonic ETL stack
  - ✅ Added PyIceberg data lakehouse storage to `polars_etl.py`
  - ✅ Created shared Iceberg catalog configuration (`iceberg_config.py`)
  - ✅ Implemented Iceberg table creation with proper schema
  - ✅ Added bulk write (overwrite) and incremental merge (upsert) operations
  - ✅ Implemented data validation and schema enforcement
  - ✅ Performance: ~0.4s bulk write, ~2.2s incremental merge (100K records)
  - _Requirements: 1.1, 2.3, 4.2_

- [x] 8.2 Enhance Spark ETL stack with Apache Iceberg support
  - ✅ Added Apache Iceberg table format support to `spark_etl.py`
  - ✅ Implemented Spark-Iceberg integration using Iceberg Spark Runtime 4.0
  - ✅ Ensured consistent table schema with Polars implementation
  - ✅ Added Iceberg catalog integration (Hadoop catalog)
  - ✅ Implemented SQL MERGE for incremental processing
  - ✅ Auto-detection of Iceberg JAR from ~/.ivy2/
  - ✅ Performance: ~37s bulk write, ~38s incremental merge (100K records)
  - _Requirements: 1.1, 2.3, 4.2_

- [x] 9. Implement detailed ETL timing and performance analysis



- [x] 9.1 Add granular timing metrics to ETL scripts


  - Track container/image metrics (size, build time, startup time)
  - Track Spark session initialization time separately
  - Break down ETL phases: Extract, Transform, Load with sub-metrics
  - Add resource monitoring (memory, CPU, throughput)
  - Export detailed timing data to JSON
  - _Requirements: 3.1, 3.2, 4.4_

- [x] 9.2 Create comprehensive performance report generator


  - Generate reports for small, medium, large datasets
  - Create timing breakdown tables and charts
  - Identify performance bottlenecks by phase
  - Compare overhead percentages across frameworks
  - Export to JSON, CSV, and Markdown formats
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 10. Deploy AWS infrastructure with Terraform (ESSENTIAL FOR EKS)
- [x] 10.1 Create Terraform modules for EKS, S3, ECR, and IAM





  - Create `terraform/` directory with modules for EKS cluster, S3 bucket, ECR repositories
  - Configure EKS cluster (v1.28+) with VPC, subnets across 3 AZs
  - Create node groups: `spark_workers` (r6i.2xlarge, 2-10 nodes), `polars_workers` (r6i.8xlarge, 0-2 nodes)
  - Create S3 bucket `etl-benchmark-data-{account_id}` with versioning
  - Create ECR repositories: `spark-etl` and `polars-etl`
  - Configure IAM roles for EKS nodes with S3 read/write permissions
  - Add Makefile targets: `make tf-init`, `make tf-plan`, `make tf-apply`, `make tf-destroy`
  - _Requirements: 2.3, 6.1, 6.2_

- [x] 11. Install Spark Operator and configure EKS for Spark workloads




- [x] 11.1 Deploy Spark Operator to EKS using Helm


  - Install Spark Operator (v1.3.0+) using Helm chart
  - Create `spark-operator` namespace
  - Configure RBAC permissions and ServiceAccount
  - Create IAM role for ServiceAccount (IRSA) with S3 access
  - Verify Spark Operator is running: `kubectl get pods -n spark-operator`
  - _Requirements: 2.2, 2.3, 6.2_

- [-] 11.2 Create SparkApplication manifest for benchmark

  - Write `k8s/spark-application.yaml` with driver/executor configuration
  - Configure Spark properties for S3 access (s3a filesystem)
  - Set resource requests/limits: driver (2 cores, 4GB), executor (4 cores, 8GB, 3 instances)
  - Add environment variables for S3 bucket path and AWS region
  - Configure dynamic allocation and executor scaling
  - Test deployment: `kubectl apply -f k8s/spark-application.yaml`
  - _Requirements: 1.1, 2.2, 2.3, 6.2_

- [ ] 12. Build and deploy container images to ECR
- [ ] 12.1 Update Dockerfiles for S3 compatibility
  - Update `Dockerfile.spark` with AWS Hadoop libraries for S3 access
  - Update `Dockerfile.polars` with boto3 and s3fs for S3 access
  - Add AWS SDK dependencies and configure credentials provider
  - Test local builds: `docker buildx build --platform linux/arm64 -t spark-etl:latest -f Dockerfile.spark .
  - _Requirements: 2.1, 2.3_

- [ ] 12.2 Push images to ECR
  - Authenticate with ECR: `aws ecr get-login-password | docker login`
  - Tag images with ECR repository URLs
  - Push spark-etl image to ECR
  - Push polars-etl image to ECR
  - Add Makefile targets: `make ecr-login`, `make ecr-push-spark`, `make ecr-push-polars`
  - _Requirements: 2.1, 2.3_

- [ ] 13. Update ETL code for S3 compatibility
- [ ] 13.1 Modify Polars ETL for S3 paths
  - Update `polars_etl.py` to support `s3://` paths using s3fs
  - Add S3 path validation and bucket existence checks
  - Implement retry logic for S3 transient errors
  - Update Iceberg catalog for S3-backed warehouse
  - Test with local S3 (MinIO) first, then AWS S3
  - _Requirements: 1.1, 2.3, 4.2, 6.2_

- [ ] 13.2 Modify Spark ETL for S3 paths
  - Update `spark_etl.py` to use `s3a://` protocol
  - Configure Spark session with S3A filesystem settings
  - Add AWS credentials provider configuration
  - Update Iceberg catalog for S3-backed warehouse
  - Test S3 read/write with sample data
  - _Requirements: 1.1, 2.3, 4.2, 6.2_

- [ ] 14. Generate benchmark datasets directly on EKS and save to S3
- [ ] 14.1 Extend data generator for cloud-scale datasets with S3 support
  - Update `ClickstreamDataGenerator` to support direct S3 writes using s3fs/boto3
  - Add dataset sizes: `tiny` (1M), `small` (10M), `medium` (50M), `large` (100M), `xlarge` (250M)
  - Add complexity levels: `simple` (basic operations) and `complex` (multi-level aggregations, joins)
  - Implement chunked generation to avoid memory exhaustion (write in 10M record batches)
  - Add progress tracking and ETA for large datasets
  - Optimize Parquet writing with appropriate row group sizes (1M rows per group)
  - Support both bulk and incremental data generation patterns
  - _Requirements: 4.3, 6.4_

- [ ] 14.2 Create Kubernetes Job manifest for data generation
  - Write `k8s/data-generator-job.yaml` with configurable dataset size and complexity
  - Configure to use Polars worker node (high memory) with IRSA for S3 access
  - Set resource requests: 32 vCPU, 128GB RAM for large datasets
  - Add job completion tracking and automatic cleanup
  - Support both x86 (r6i) and Graviton (r6g) instance types
  - _Requirements: 2.3, 6.2, 6.4_

- [ ] 14.3 Create data generation orchestration script
  - Write `scripts/generate_benchmark_datasets.py` to generate all 8 benchmark datasets
  - Dataset matrix: tiny, small, medium, large, xlarge (simple) + medium-complex, large-complex, xlarge-complex
  - Submit Kubernetes Jobs for each dataset with proper naming and S3 paths
  - Monitor job progress and collect generation metrics (time, cost)
  - Verify data integrity after generation (record counts, file sizes)
  - Add Makefile targets: `make eks-generate-data SIZE=medium COMPLEXITY=simple`
  - Add target for all datasets: `make eks-generate-all-datasets`
  - _Requirements: 2.3, 4.2, 4.3, 6.4_

- [ ] 14.4 Document benchmark strategy and cost estimates
  - Create comprehensive benchmark strategy document (see `docs/benchmark-strategy.md`)
  - Define 8 datasets to identify Spark vs Polars crossover point
  - Document expected crossover: 50-100M records (simple), 25-50M (complex)
  - Calculate infrastructure costs: Graviton saves 20% vs x86
  - Estimate benchmark costs: ~$20-25 per full benchmark cycle (8 datasets × 2 frameworks)
  - Provide instance type recommendations (r6g.2xlarge for Spark, r6g.8xlarge for Polars)
  - _Requirements: 6.4, 7.1, 7.2_

- [ ] 15. Run benchmarks on EKS and collect results
- [ ] 15.1 Create EKS benchmark orchestration script
  - Write `scripts/run_eks_benchmark.py` to submit Spark and Polars jobs
  - Implement kubectl integration for job creation and monitoring
  - Add job status polling and completion detection
  - Implement log collection from completed pods
  - Add timeout handling and job cancellation
  - Create Makefile target: `make eks-benchmark SIZE=xlarge`
  - _Requirements: 1.2, 2.3, 5.1_

- [ ] 15.2 Collect metrics and generate reports
  - Query CloudWatch Container Insights for pod metrics (CPU, memory, network)
  - Collect S3 request metrics (GET/PUT counts, bytes transferred)
  - Download benchmark results from S3 to local machine
  - Generate performance report with cost analysis
  - Update PowerPoint generator with cloud benchmark results
  - Add Makefile target: `make eks-results`
  - _Requirements: 1.2, 3.1, 3.2, 6.5, 7.1, 7.2_
