# Implementation Plan: TPC-H Benchmark POC

## Overview

This implementation plan breaks down the TPC-H benchmark POC into discrete, incremental tasks. Each task builds on previous work and includes testing to validate correctness. The plan follows a logical progression: data generation → baseline implementation → challenger implementation → orchestration → analysis.

**Note**: This is a **strategic pivot** from the existing NYC Taxi benchmark. The project already has:
- ✅ Existing `src/` structure with `analysis/`, `etl/`, `utils/` directories
- ✅ NYC Taxi ETL implementations (Polars and Spark)
- ✅ Analysis infrastructure (cost calculator, crossover analyzer, TCO analyzer)
- ✅ Most dependencies already configured in `pyproject.toml`

Tasks are written to **adapt and extend** existing code rather than create from scratch.

## Tasks

- [x] 1. Adapt existing project for TPC-H benchmark pivot
  - Add src/generation/ directory for TPC-H data generation
  - Add src/orchestration/ directory for multi-job orchestration
  - Update pyproject.toml to add missing dependencies: boto3, hypothesis (duckdb, polars, pyarrow, pyspark, pytest already present)
  - Create/update .env.example with TPC-H-specific environment variables (S3_BUCKET_NAME, EKS_CLUSTER_NAME, BATCH_JOB_QUEUE, BATCH_JOB_DEFINITION)
  - Review existing logging configuration in src/utils/
  - _Requirements: 6.2, 6.5, 7.5, 10.2_

- [ ]* 1.1 Write unit tests for new directory structure
  - Test that src/generation/ and src/orchestration/ directories exist
  - Test that TPC-H environment variables can be loaded
  - _Requirements: 6.2_

- [x] 2. Implement TPC-H data generator using tpchgen-rs
  - [x] 2.1 Create Python wrapper for tpchgen-rs CLI
    - Check if tpchgen-cli is installed (cargo install tpchgen-cli)
    - Execute tpchgen-cli with scale factor and output directory
    - Capture stdout/stderr for progress logging
    - Handle errors if tpchgen-cli is not found
    - Provide clear installation instructions if missing
    - **Implementation**: `src/generation/tpchgen_wrapper.py`
    - _Requirements: 1.1, 1.6, 1.8_

  - [ ]* 2.2 Write property test for tpchgen-rs execution
    - **Property 1: TPC-H Table Generation Completeness**
    - **Validates: Requirements 1.1**

  - [x] 2.3 Implement local Parquet generation with streaming
    - Use tpchgen-cli --format=parquet to generate files locally
    - Verify all 8 tables are generated
    - Log generation time and file sizes
    - Ensure constant memory usage (~2GB) regardless of scale factor
    - **Implementation**: `src/generation/generate_tpch_data_fast.py` (local generation)
    - _Requirements: 1.2, 1.6_

  - [ ]* 2.4 Write property test for Parquet output
    - **Property 2: Parquet Output Validation**
    - **Validates: Requirements 1.2**

  - [x] 2.5 Implement S3 upload using AWS CLI
    - Use aws s3 sync to upload generated Parquet files to S3
    - Maintain directory structure during upload
    - Show upload progress for large files
    - Clean up local files after successful upload (unless --keep-local flag)
    - **Implementation**: Integrated in both `generate_tpch_data_fast.py` and `generate_on_ec2.py`
    - _Requirements: 1.3, 1.7_

  - [ ]* 2.6 Write property test for S3 upload
    - **Property 3: S3 Upload Completeness**
    - **Validates: Requirements 1.3**

  - [x] 2.7 Add scale factor configuration
    - Support SF 10 (~6 seconds) and SF 100 (~45 seconds) via command-line argument
    - Validate scale factor is positive integer
    - Log dataset size and generation time
    - **Implementation**: Both scripts support `--scale-factor` argument
    - _Requirements: 1.4_

  - [ ]* 2.8 Write property test for scale factor support
    - **Property 4: Scale Factor Support**
    - **Validates: Requirements 1.4**

  - [ ]* 2.9 Write property test for generation logging
    - **Property 5: Generation Progress Logging**
    - **Validates: Requirements 1.5**

  - [ ]* 2.10 Write property test for constant memory usage
    - **Property 6: Constant Memory Usage**
    - **Validates: Requirements 1.6**

  - [x] 2.11 Implement EC2-based generation for large scale factors
    - Launch EC2 instance with appropriate resources
    - Install Rust and tpchgen-cli on EC2
    - Generate data on EC2 and upload to S3 via fast internal network
    - Automatic instance termination and cleanup
    - **Implementation**: `src/generation/generate_on_ec2.py`
    - _Requirements: 1.3, 1.4, 1.7_

- [ ] 3. Checkpoint - Verify data generation
  - Run generator with SF 10 and verify all tables created
  - Check S3 structure matches expected layout
  - Ensure all tests pass, ask the user if questions arise

- [ ] 4. Implement PySpark ETL baseline
  - [ ] 4.1 Create SparkETLJob class
    - Initialize SparkSession with S3 configuration
    - Implement load_tables() to read Parquet from S3
    - Validate table schemas match TPC-H specification
    - _Requirements: 2.1_

  - [ ] 4.2 Implement TPC-H Query 3 (Shipping Priority)
    - Join customer, orders, and lineitem tables
    - Apply filters: c_mktsegment, o_orderdate, l_shipdate
    - Aggregate by l_orderkey with revenue calculation
    - Order by revenue descending and limit to top 10
    - _Requirements: 2.2_

  - [ ]* 4.3 Write property test for query result equivalence
    - **Property 6: Query Result Equivalence**
    - **Validates: Requirements 2.2**

  - [ ] 4.4 Implement PerformanceTracker class
    - Track startup time (job submission to execution start)
    - Track execution time (data read to result write)
    - Track peak memory usage via Spark metrics
    - Track bytes read and written from S3
    - _Requirements: 2.3, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 4.5 Write property test for complete metrics collection
    - **Property 7: Complete Metrics Collection**
    - **Validates: Requirements 2.3, 3.6, 8.1, 8.2, 8.3, 8.4**

  - [ ] 4.6 Write results and metrics to S3
    - Write query results as Parquet
    - Write metrics as JSON with all required fields
    - _Requirements: 2.5, 8.5_

  - [ ]* 4.7 Write property test for metrics persistence
    - **Property 8: Metrics Persistence**
    - **Validates: Requirements 8.5**

  - [ ] 4.8 Create SparkApplication Kubernetes manifest
    - Define SparkApplication CRD for Spark Operator
    - Configure executor count and resources
    - Set up Pod Identity Association for S3 access
    - _Requirements: 2.4_

- [ ] 5. Implement Polars + DuckDB ETL challenger
  - [ ] 5.1 Create PolarsETLJob class for TPC-H (adapt from existing PolarsNYCTaxiETL)
    - Initialize DuckDB connection with httpfs extension
    - Configure S3 credentials for DuckDB
    - Reuse existing PipelineTimer for performance tracking
    - _Requirements: 3.1_

  - [ ] 5.2 Implement query with predicate pushdown
    - Use DuckDB to apply filters at storage layer
    - Measure bytes read with and without pushdown
    - Log pushdown efficiency metrics
    - _Requirements: 3.2, 9.5_

  - [ ]* 5.3 Write property test for predicate pushdown efficiency
    - **Property 9: Predicate Pushdown Efficiency**
    - **Validates: Requirements 3.2, 9.5**

  - [ ] 5.4 Implement query with projection pushdown
    - Use DuckDB to select only required columns
    - Measure bytes read with and without projection
    - Log projection efficiency metrics
    - _Requirements: 3.3_

  - [ ]* 5.5 Write property test for projection pushdown efficiency
    - **Property 10: Projection Pushdown Efficiency**
    - **Validates: Requirements 3.3**

  - [ ] 5.6 Implement zero-copy handoff to Polars
    - Execute DuckDB query to get relation object
    - Use duckdb_rel.pl() for zero-copy transfer
    - Verify no serialization occurs
    - _Requirements: 3.4_

  - [ ] 5.7 Implement Polars streaming mode
    - Use pl.scan_parquet() for lazy evaluation
    - Apply transformations (filter, group_by, agg)
    - Use .collect(streaming=True) for out-of-core processing
    - _Requirements: 3.5_

  - [ ] 5.8 Implement TPC-H Query 3 logic
    - Match PySpark query exactly (same filters, joins, aggregations)
    - Verify results match PySpark output
    - _Requirements: 2.2_

  - [ ] 5.9 Adapt performance tracking from existing PipelineTimer
    - Reuse timing_decorator.py infrastructure
    - Track same metrics as PySpark for fair comparison
    - _Requirements: 3.6_

  - [ ] 5.10 Write results and metrics to S3
    - Write query results as Parquet using PyArrow
    - Write metrics as JSON (adapt existing metrics format)
    - _Requirements: 2.5, 8.5_

  - [ ] 5.11 Create AWS Batch job definition
    - Define Fargate task with configurable vCPU and memory
    - Set up IAM role for S3 access
    - Configure CloudWatch Logs integration
    - _Requirements: 3.7_

  - [ ]* 5.12 Write property test for partition pruning
    - **Property 11: Partition Pruning Efficiency**
    - **Validates: Requirements 9.4**

- [ ] 6. Checkpoint - Verify both ETL implementations
  - Run both PySpark and Polars jobs on same data
  - Verify results are identical
  - Compare metrics and validate tracking
  - Ensure all tests pass, ask the user if questions arise

- [ ] 7. Implement multi-job orchestrator
  - [ ] 7.1 Create JobOrchestrator class
    - Initialize with EKS cluster name and Batch job queue
    - Set up boto3 clients for EKS and Batch
    - _Requirements: 4.1, 4.2_

  - [ ] 7.2 Implement Spark job submission
    - Use Kubernetes API to create SparkApplication resources
    - Submit 10 jobs concurrently
    - Record job creation timestamps
    - _Requirements: 4.1_

  - [ ]* 7.3 Write property test for Spark job submission
    - **Property 12: Concurrent Job Submission (Spark)**
    - **Validates: Requirements 4.1**

  - [ ] 7.4 Implement Batch job submission
    - Use boto3 to submit jobs to AWS Batch
    - Submit 10 jobs concurrently
    - Record job creation timestamps
    - _Requirements: 4.2_

  - [ ]* 7.5 Write property test for Batch job submission
    - **Property 12: Concurrent Job Submission (Batch)**
    - **Validates: Requirements 4.2**

  - [ ] 7.6 Implement job monitoring
    - Poll job status every 5 seconds
    - Record "Job Started" timestamp when execution begins
    - Record "Job Completed" timestamp when finished
    - _Requirements: 4.3_

  - [ ]* 7.7 Write property test for timestamp recording
    - **Property 13: Timestamp Recording**
    - **Validates: Requirements 4.3**

  - [ ] 7.8 Calculate startup latency
    - Compute delta: started_at - created_at
    - Validate latency is non-negative
    - Store latency in job metrics
    - _Requirements: 4.4_

  - [ ]* 7.9 Write property test for startup latency calculation
    - **Property 14: Startup Latency Calculation**
    - **Validates: Requirements 4.4**

  - [ ] 7.10 Collect metrics from all jobs
    - Wait for all 20 jobs to complete
    - Download metrics JSON from S3 for each job
    - Aggregate into single dataset
    - _Requirements: 4.5_

  - [ ]* 7.11 Write property test for complete metrics collection
    - **Property 15: Complete Metrics Collection from All Jobs**
    - **Validates: Requirements 4.5**

- [ ] 8. Implement analysis dashboard
  - [ ] 8.1 Adapt MetricsAnalyzer class (leverage existing src/analysis/ modules)
    - Extend existing cost_calculator.py for TPC-H metrics
    - Load metrics JSON files from S3
    - Parse into pandas DataFrame
    - _Requirements: 5.1_

  - [ ]* 8.2 Write property test for metrics extraction
    - **Property 16: Metrics Extraction from Logs**
    - **Validates: Requirements 5.1**

  - [ ] 8.3 Calculate performance statistics
    - Compute mean, median, p95 for all metrics
    - Group by job type (Spark vs Polars)
    - Adapt existing crossover_analyzer.py logic
    - _Requirements: 5.1_

  - [ ] 8.4 Implement cost calculation for TPC-H benchmark
    - Extend existing cost_calculator.py with TPC-H pricing
    - Calculate EKS costs: control plane + node costs
    - Calculate Batch costs: vCPU + memory costs
    - Compute cost-per-GB-processed
    - _Requirements: 5.3, 5.4_

  - [ ]* 8.5 Write property test for cost calculation accuracy
    - **Property 18: Cost Calculation Accuracy**
    - **Validates: Requirements 5.3**

  - [ ]* 8.6 Write property test for cost metrics in report
    - **Property 19: Cost Metrics in Report**
    - **Validates: Requirements 5.4**

  - [ ] 8.7 Generate Markdown comparison report
    - Create table with performance metrics side-by-side
    - Include cost analysis section
    - Highlight winner for each metric
    - _Requirements: 5.2_

  - [ ]* 8.8 Write property test for Markdown report generation
    - **Property 17: Markdown Report Generation**
    - **Validates: Requirements 5.2**

  - [ ] 8.9 Add startup latency analysis
    - Calculate mean, median, p95 for startup latency
    - Compare EKS vs Batch startup times
    - Include in report with interpretation
    - _Requirements: 5.5_

  - [ ]* 8.10 Write property test for startup latency comparison
    - **Property 20: Startup Latency Comparison**
    - **Validates: Requirements 5.5**

  - [ ] 8.11 Generate summary report
    - Synthesize key findings
    - Provide recommendations based on results
    - Include decision framework
    - _Requirements: 10.4_

  - [ ]* 8.12 Write property test for summary report generation
    - **Property 26: Summary Report Generation**
    - **Validates: Requirements 10.4**

- [ ] 9. Implement code quality standards
  - [ ] 9.1 Add type hints to all functions
    - Review all function signatures
    - Add type hints for parameters and return values
    - Run mypy to validate type correctness
    - _Requirements: 6.1_

  - [ ]* 9.2 Write property test for type hint coverage
    - **Property 21: Type Hint Coverage**
    - **Validates: Requirements 6.1**

  - [ ] 9.3 Add exception handling
    - Wrap S3 operations in try/except blocks
    - Wrap API calls in try/except blocks
    - Log all exceptions with stack traces
    - _Requirements: 6.3_

  - [ ]* 9.4 Write property test for exception handling coverage
    - **Property 22: Exception Handling Coverage**
    - **Validates: Requirements 6.3**

  - [ ] 9.5 Add docstrings to all public functions
    - Write docstrings with purpose, parameters, and return values
    - Follow Google or NumPy docstring format
    - _Requirements: 6.4_

  - [ ]* 9.6 Write property test for docstring coverage
    - **Property 23: Docstring Coverage**
    - **Validates: Requirements 6.4**

  - [ ] 9.7 Ensure environment variable configuration
    - Replace any hardcoded values with env vars
    - Validate all required env vars at startup
    - _Requirements: 6.5, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 9.8 Write property test for environment variable configuration
    - **Property 24: Environment Variable Configuration**
    - **Validates: Requirements 6.5, 7.1, 7.2, 7.3, 7.4**

  - [ ] 9.9 Implement debug logging control
    - Add DEBUG environment variable check
    - Enable verbose logging when DEBUG=true
    - Use standard logging levels otherwise
    - _Requirements: 10.5_

  - [ ]* 9.10 Write property test for debug logging control
    - **Property 27: Debug Logging Control**
    - **Validates: Requirements 10.5**

- [ ] 10. Update documentation for TPC-H pivot
  - Update README.md with TPC-H benchmark overview and architecture
  - Document TPC-H setup steps: data generation, AWS Batch configuration
  - Document how to run TPC-H data generation
  - Document how to run TPC-H benchmarks (EKS + Batch)
  - Document how to analyze TPC-H results
  - _Requirements: 10.1, 10.3_

- [ ] 11. Final checkpoint - End-to-end validation
  - Run complete benchmark: generation → execution → analysis
  - Verify all 20 jobs complete successfully
  - Review generated reports for accuracy
  - Validate cost calculations against AWS pricing
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The implementation follows clean code principles with type hints, docstrings, and proper error handling
