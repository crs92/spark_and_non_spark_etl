# Requirements Document

## Introduction

This Senior Data Engineering POC demonstrates a strategic pivot from Spark on EKS to a Job-Native Polars/DuckDB architecture on AWS Batch. The goal is to prove that single-node, high-performance engines are more cost-effective and faster for datasets up to 100GB.

The benchmark uses **TPC-H standard benchmark data** to provide industry-standard, reproducible performance testing. By comparing PySpark on EKS against Polars/DuckDB on AWS Batch, we demonstrate:

1. **Performance characteristics** for complex joins and aggregations
2. **Infrastructure complexity** (Kubernetes cluster vs. serverless batch jobs)
3. **Cost efficiency** (vCPU/hour for EKS nodes vs. Fargate/Batch tasks)
4. **Startup latency** (EKS pod scheduling vs. Batch job launch)
5. **Scalability patterns** (horizontal scaling vs. vertical scaling with out-of-core processing)

This POC answers the critical question: **"When should we use single-node high-performance engines instead of distributed systems?"**

## Glossary

- **TPC-H**: Transaction Processing Performance Council - Decision Support Benchmark, an industry-standard benchmark for analytical workloads
- **Scale Factor**: TPC-H parameter controlling dataset size (SF 10 = ~10GB, SF 100 = ~100GB)
- **Predicate Pushdown**: Filtering data at the storage layer before loading into memory
- **Projection Pushdown**: Selecting only required columns at the storage layer
- **Zero-Copy Handoff**: Passing data between systems without serialization/deserialization overhead
- **Out-of-Core Processing**: Processing datasets larger than available RAM using streaming techniques
- **AWS Batch**: Managed batch computing service that runs jobs on Fargate or EC2
- **EKS**: Amazon Elastic Kubernetes Service
- **Startup Latency**: Time between job submission and actual execution start

## Requirements

### Requirement 1: TPC-H Synthetic Data Generation

**User Story:** As a benchmark engineer, I want to generate TPC-H standard benchmark data at scale factors 10 and 100 using tpchgen-rs (20x faster than alternatives), so that I can test performance on industry-standard datasets of 10GB and 100GB without waiting hours.

#### Acceptance Criteria

1. WHEN generating data THEN the system SHALL use tpchgen-rs CLI tool to create all 8 TPC-H tables (customer, lineitem, nation, orders, part, partsupp, region, supplier)
2. WHEN writing data THEN the system SHALL output Parquet files directly to local storage with streaming generation (constant memory usage)
3. WHEN uploading data THEN the system SHALL upload generated Parquet files to S3 using AWS CLI after generation completes
4. WHEN configuring scale THEN the system SHALL support Scale Factor 10 (~10GB, ~6 seconds) and Scale Factor 100 (~100GB, ~45 seconds)
5. WHEN executing generation THEN the system SHALL log progress and completion time for the entire dataset
6. WHEN generating data THEN the system SHALL use constant memory (~2GB) regardless of scale factor
7. WHEN cleaning up THEN the system SHALL remove local temporary files after successful S3 upload (unless --keep-local flag is used)
8. WHEN tpchgen-rs is not installed THEN the system SHALL provide clear installation instructions (cargo install tpchgen-cli)

### Requirement 2: PySpark Legacy Baseline Implementation

**User Story:** As a performance engineer, I want a PySpark implementation that reads TPC-H data from S3 and performs complex joins and aggregations, so that I can establish a baseline for distributed processing performance.

#### Acceptance Criteria

1. WHEN reading data THEN the PySpark job SHALL load TPC-H tables from S3 in Parquet format
2. WHEN processing data THEN the job SHALL execute a complex query mimicking TPC-H Query 3 or Query 5 (multi-table joins with aggregations)
3. WHEN measuring performance THEN the job SHALL track startup time (job submission to execution start), total execution time, and peak memory usage
4. WHEN running on EKS THEN the job SHALL use the Spark Operator for native Kubernetes integration
5. WHEN writing results THEN the job SHALL output aggregated results to S3

### Requirement 3: Polars + DuckDB Innovative Challenger Implementation

**User Story:** As a data engineer, I want a Polars/DuckDB implementation optimized for AWS Batch that uses predicate pushdown, zero-copy handoff, and streaming mode, so that I can process 100GB datasets on machines with only 16-32GB RAM.

#### Acceptance Criteria

1. WHEN reading data THEN the system SHALL use DuckDB with httpfs extension to query S3 directly
2. WHEN filtering data THEN the system SHALL apply predicate pushdown to filter at the storage layer
3. WHEN selecting columns THEN the system SHALL apply projection pushdown to read only required columns
4. WHEN transferring to Polars THEN the system SHALL use zero-copy handoff via duckdb_rel.pl()
5. WHEN processing large datasets THEN the system SHALL use Polars streaming mode (.collect(streaming=True)) to enable out-of-core processing
6. WHEN measuring performance THEN the system SHALL track the same metrics as PySpark (startup time, execution time, peak memory)
7. WHEN running on AWS Batch THEN the system SHALL execute as a Fargate task with configurable vCPU and memory

### Requirement 4: Multi-Job Orchestration Stress Test

**User Story:** As a DevOps engineer, I want to trigger 10 concurrent instances of both Spark and Polars jobs, so that I can measure startup latency and demonstrate EKS scheduling overhead.

#### Acceptance Criteria

1. WHEN orchestrating jobs THEN the system SHALL use boto3 to trigger 10 Spark jobs on EKS
2. WHEN orchestrating jobs THEN the system SHALL use boto3 to trigger 10 Polars jobs on AWS Batch
3. WHEN logging timestamps THEN the system SHALL record "Job Created" and "Job Started" times for each job
4. WHEN calculating latency THEN the system SHALL compute the delta between job creation and execution start
5. WHEN jobs complete THEN the system SHALL collect execution metrics from all 20 jobs (10 Spark + 10 Polars)

### Requirement 5: Comparison Dashboard and Cost Analysis

**User Story:** As a technical leader, I want a comparison dashboard that shows performance metrics and cost estimates, so that I can make data-driven decisions about technology selection.

#### Acceptance Criteria

1. WHEN parsing logs THEN the system SHALL extract execution time, memory usage, and startup latency from both Spark and Polars runs
2. WHEN generating reports THEN the system SHALL create a Markdown table comparing all metrics side-by-side
3. WHEN calculating costs THEN the system SHALL use AWS pricing for EKS nodes (vCPU/hour) and Batch Fargate tasks (vCPU/hour + memory/GB/hour)
4. WHEN presenting results THEN the system SHALL show cost-per-GB-processed and total cost for each approach
5. WHEN analyzing startup latency THEN the system SHALL highlight the difference in "Job Created" to "Job Started" times between EKS and Batch

### Requirement 6: Clean Code and Senior-Level Quality

**User Story:** As a code reviewer, I want all code to follow clean code principles suitable for a Senior POC, so that the implementation demonstrates professional engineering standards.

#### Acceptance Criteria

1. WHEN writing code THEN the system SHALL use type hints for all function signatures
2. WHEN organizing code THEN the system SHALL separate concerns into modules (data generation, ETL logic, orchestration, analysis)
3. WHEN handling errors THEN the system SHALL include proper exception handling and logging
4. WHEN documenting code THEN the system SHALL include docstrings for all public functions
5. WHEN configuring THEN the system SHALL use environment variables for AWS credentials and S3 bucket names

### Requirement 7: AWS Infrastructure Configuration

**User Story:** As a cloud engineer, I want all AWS resources to be configurable via environment variables, so that the POC can run in any AWS account without code changes.

#### Acceptance Criteria

1. WHEN accessing S3 THEN the system SHALL read bucket names from environment variables (S3_BUCKET_NAME)
2. WHEN authenticating THEN the system SHALL use AWS credentials from environment variables or IAM roles
3. WHEN configuring EKS THEN the system SHALL read cluster name from environment variables (EKS_CLUSTER_NAME)
4. WHEN configuring Batch THEN the system SHALL read job queue and job definition from environment variables (BATCH_JOB_QUEUE, BATCH_JOB_DEFINITION)
5. WHEN deploying THEN the system SHALL provide example .env files with all required variables

### Requirement 8: Performance Measurement and Observability

**User Story:** As a performance analyst, I want detailed metrics collection for both implementations, so that I can accurately compare performance characteristics.

#### Acceptance Criteria

1. WHEN measuring startup time THEN the system SHALL record the time from job submission to first line of code execution
2. WHEN measuring execution time THEN the system SHALL record the time from data read start to result write completion
3. WHEN measuring memory THEN the system SHALL track peak memory usage during execution
4. WHEN measuring I/O THEN the system SHALL track bytes read from S3 and bytes written to S3
5. WHEN jobs complete THEN the system SHALL write all metrics to a structured JSON file in S3

### Requirement 9: Data Lake Realism

**User Story:** As a data architect, I want the TPC-H data to be partitioned and stored like a real data lake, so that the benchmark reflects production scenarios.

#### Acceptance Criteria

1. WHEN partitioning lineitem THEN the system SHALL use Hive-style partitioning by year and month (l_shipdate)
2. WHEN writing Parquet THEN the system SHALL use appropriate compression (snappy or zstd)
3. WHEN organizing files THEN the system SHALL create a realistic file structure: s3://bucket/tpch/lineitem/year=1995/month=01/
4. WHEN reading data THEN both implementations SHALL leverage partition pruning when filtering by date
5. WHEN querying THEN the system SHALL demonstrate predicate pushdown benefits on partitioned data

### Requirement 10: Reproducibility and Documentation

**User Story:** As a developer, I want clear documentation and reproducible setup, so that I can run the entire POC from scratch.

#### Acceptance Criteria

1. WHEN setting up THEN the system SHALL provide a README with step-by-step instructions
2. WHEN installing dependencies THEN the system SHALL use requirements.txt or pyproject.toml for Python dependencies
3. WHEN running benchmarks THEN the system SHALL provide a single command to execute the full benchmark suite
4. WHEN reviewing results THEN the system SHALL generate a summary report with key findings
5. WHEN troubleshooting THEN the system SHALL include debug logging that can be enabled via environment variable
