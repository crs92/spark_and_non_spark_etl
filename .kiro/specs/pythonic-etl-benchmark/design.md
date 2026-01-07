# Design Document

## Overview

This POC implements a comprehensive comparison between traditional distributed processing (PySpark on EKS) and modern single-node high-performance engines (Polars + DuckDB on AWS Batch). The system consists of five major components:

1. **TPC-H Data Generator**: Creates industry-standard benchmark data at configurable scales
2. **PySpark ETL Baseline**: Implements complex analytical queries on EKS with full observability
3. **Polars/DuckDB ETL Challenger**: Implements the same queries using modern optimization techniques on AWS Batch
4. **Multi-Job Orchestrator**: Stress-tests both systems with concurrent job execution
5. **Analysis Dashboard**: Compares performance and cost metrics

The design emphasizes **clean separation of concerns**, **reproducibility**, and **production-grade code quality** suitable for a Senior Data Engineering POC.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
│                                                                   │
│  ┌──────────────────┐                                            │
│  │  TPC-H Generator │                                            │
│  │    (DuckDB)      │──────┐                                     │
│  └──────────────────┘      │                                     │
│                             ▼                                     │
│                      ┌─────────────┐                             │
│                      │  S3 Bucket  │                             │
│                      │  TPC-H Data │                             │
│                      │  (Parquet)  │                             │
│                      └─────────────┘                             │
│                        │         │                               │
│           ┌────────────┘         └────────────┐                  │
│           ▼                                   ▼                  │
│  ┌─────────────────┐                 ┌──────────────────┐       │
│  │   EKS Cluster   │                 │   AWS Batch      │       │
│  │                 │                 │   (Fargate)      │       │
│  │  ┌───────────┐  │                 │                  │       │
│  │  │  Spark    │  │                 │  ┌────────────┐  │       │
│  │  │ Operator  │  │                 │  │  Polars +  │  │       │
│  │  └───────────┘  │                 │  │  DuckDB    │  │       │
│  │       │         │                 │  │   Job      │  │       │
│  │       ▼         │                 │  └────────────┘  │       │
│  │  ┌───────────┐  │                 │                  │       │
│  │  │ PySpark   │  │                 └──────────────────┘       │
│  │  │   Jobs    │  │                          │                 │
│  │  └───────────┘  │                          │                 │
│  └─────────────────┘                          │                 │
│           │                                    │                 │
│           └────────────┬───────────────────────┘                 │
│                        ▼                                         │
│                 ┌─────────────┐                                  │
│                 │  S3 Bucket  │                                  │
│                 │   Results   │                                  │
│                 │  & Metrics  │                                  │
│                 └─────────────┘                                  │
│                        │                                         │
│                        ▼                                         │
│                 ┌─────────────┐                                  │
│                 │  Analysis   │                                  │
│                 │  Dashboard  │                                  │
│                 └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **Data Generation Phase**:
   - TPC-H Generator runs locally or on EC2
   - Generates data using DuckDB's TPC-H extension
   - Writes partitioned Parquet files directly to S3

2. **Benchmark Execution Phase**:
   - Orchestrator submits jobs to both EKS and AWS Batch
   - PySpark jobs run on EKS via Spark Operator
   - Polars/DuckDB jobs run on AWS Batch Fargate
   - Both read from same S3 TPC-H data
   - Both write results and metrics to S3

3. **Analysis Phase**:
   - Analysis script reads metrics from S3
   - Calculates performance and cost comparisons
   - Generates Markdown reports and visualizations

## Components and Interfaces

### Component 1: TPC-H Data Generator

**Purpose**: Generate industry-standard TPC-H benchmark data at configurable scales.

**Technology Stack**: Python, DuckDB, boto3

**Key Classes**:

```python
class TPCHGenerator:
    """Generates TPC-H data and writes to S3."""

    def __init__(self, scale_factor: int, s3_bucket: str, s3_prefix: str):
        """
        Initialize generator.

        Args:
            scale_factor: TPC-H scale factor (10 = ~10GB, 100 = ~100GB)
            s3_bucket: Target S3 bucket name
            s3_prefix: S3 prefix for TPC-H data
        """

    def generate_all_tables(self) -> None:
        """Generate all 8 TPC-H tables and write to S3."""

    def generate_table(self, table_name: str, partition_by: Optional[str] = None) -> None:
        """
        Generate a single TPC-H table.

        Args:
            table_name: Name of TPC-H table (e.g., 'lineitem', 'orders')
            partition_by: Optional column to partition by (for lineitem: 'l_shipdate')
        """
```

**Implementation Details**:
- Uses DuckDB's built-in TPC-H extension: `CALL dbgen(sf=10)`
- Partitions lineitem table by year/month extracted from l_shipdate
- Writes Parquet with Snappy compression
- Uses DuckDB's S3 extension for direct writes (no local storage)
- Logs progress for each table generation

**S3 Structure**:
```
s3://bucket/tpch-sf10/
  ├── customer/
  │   └── data.parquet
  ├── lineitem/
  │   ├── year=1992/month=01/data.parquet
  │   ├── year=1992/month=02/data.parquet
  │   └── ...
  ├── nation/
  ├── orders/
  ├── part/
  ├── partsupp/
  ├── region/
  └── supplier/
```

### Component 2: PySpark ETL Baseline

**Purpose**: Implement TPC-H Query 3 or 5 using PySpark on EKS as the distributed processing baseline.

**Technology Stack**: PySpark, Kubernetes, Spark Operator

**Key Classes**:

```python
class SparkETLJob:
    """PySpark implementation of TPC-H analytical query."""

    def __init__(self, spark: SparkSession, s3_input_path: str, s3_output_path: str):
        """
        Initialize Spark ETL job.

        Args:
            spark: SparkSession instance
            s3_input_path: S3 path to TPC-H data
            s3_output_path: S3 path for results
        """

    def load_tables(self) -> Dict[str, DataFrame]:
        """Load required TPC-H tables from S3."""

    def execute_query(self) -> DataFrame:
        """Execute TPC-H Query 3 or 5 with joins and aggregations."""

    def write_results(self, df: DataFrame) -> None:
        """Write aggregated results to S3."""

class PerformanceTracker:
    """Tracks performance metrics for Spark jobs."""

    def __init__(self):
        self.metrics = {
            'startup_time': 0.0,
            'execution_time': 0.0,
            'peak_memory_mb': 0,
            'bytes_read': 0,
            'bytes_written': 0
        }

    def record_startup(self, start_time: float, execution_start: float) -> None:
        """Record time from job submission to execution start."""

    def record_execution(self, start_time: float, end_time: float) -> None:
        """Record total execution time."""

    def write_metrics(self, s3_path: str) -> None:
        """Write metrics to S3 as JSON."""
```

**Query Implementation** (TPC-H Query 3 - Shipping Priority):
```sql
SELECT
    l_orderkey,
    SUM(l_extendedprice * (1 - l_discount)) AS revenue,
    o_orderdate,
    o_shippriority
FROM
    customer, orders, lineitem
WHERE
    c_mktsegment = 'BUILDING'
    AND c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate < DATE '1995-03-15'
    AND l_shipdate > DATE '1995-03-15'
GROUP BY
    l_orderkey, o_orderdate, o_shippriority
ORDER BY
    revenue DESC, o_orderdate
LIMIT 10
```

**Kubernetes Deployment**:
- Uses SparkApplication CRD (Spark Operator)
- Configurable executor count and resources
- Pod Identity Association for S3 access
- Metrics exported to CloudWatch

### Component 3: Polars/DuckDB ETL Challenger

**Purpose**: Implement the same query using modern optimization techniques on AWS Batch.

**Technology Stack**: Python, DuckDB, Polars, PyArrow, AWS Batch (Fargate)

**Key Classes**:

```python
class PolarsETLJob:
    """Polars + DuckDB implementation with optimization techniques."""

    def __init__(self, s3_input_path: str, s3_output_path: str):
        """
        Initialize Polars ETL job.

        Args:
            s3_input_path: S3 path to TPC-H data
            s3_output_path: S3 path for results
        """

    def setup_duckdb(self) -> duckdb.DuckDBPyConnection:
        """Configure DuckDB with httpfs extension for S3 access."""

    def execute_query_with_pushdown(self) -> pl.DataFrame:
        """
        Execute query using DuckDB with predicate and projection pushdown.

        Returns:
            Polars DataFrame via zero-copy handoff
        """

    def process_with_streaming(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Process data using Polars streaming mode for out-of-core execution.

        Args:
            df: Input Polars DataFrame

        Returns:
            Processed DataFrame
        """

    def write_results(self, df: pl.DataFrame) -> None:
        """Write results to S3 using PyArrow."""

class OptimizationDemo:
    """Demonstrates optimization techniques."""

    @staticmethod
    def demonstrate_predicate_pushdown() -> None:
        """Show how DuckDB filters at storage layer."""

    @staticmethod
    def demonstrate_projection_pushdown() -> None:
        """Show how DuckDB reads only required columns."""

    @staticmethod
    def demonstrate_zero_copy() -> None:
        """Show zero-copy handoff from DuckDB to Polars."""

    @staticmethod
    def demonstrate_streaming() -> None:
        """Show Polars streaming mode for out-of-core processing."""
```

**Optimization Techniques**:

1. **Predicate Pushdown**:
```python
# DuckDB applies filters at Parquet file level
query = """
SELECT * FROM read_parquet('s3://bucket/lineitem/**/*.parquet')
WHERE l_shipdate > '1995-03-15'
"""
# Only reads Parquet row groups matching the predicate
```

2. **Projection Pushdown**:
```python
# DuckDB reads only required columns
query = """
SELECT l_orderkey, l_extendedprice, l_discount
FROM read_parquet('s3://bucket/lineitem/**/*.parquet')
"""
# Skips reading unused columns, reducing I/O
```

3. **Zero-Copy Handoff**:
```python
# Transfer from DuckDB to Polars without serialization
duckdb_rel = conn.execute(query)
polars_df = duckdb_rel.pl()  # Zero-copy via Arrow
```

4. **Streaming Mode**:
```python
# Process 100GB dataset with 16GB RAM
result = (
    pl.scan_parquet('s3://bucket/lineitem/**/*.parquet')
    .filter(pl.col('l_shipdate') > '1995-03-15')
    .group_by('l_orderkey')
    .agg(pl.sum('revenue'))
    .collect(streaming=True)  # Out-of-core processing
)
```

**AWS Batch Configuration**:
- Fargate launch type (serverless)
- Configurable vCPU (4, 8, 16) and memory (16GB, 32GB, 64GB)
- IAM role for S3 access
- CloudWatch Logs integration

### Component 4: Multi-Job Orchestrator

**Purpose**: Stress-test both systems with concurrent job execution to measure startup latency.

**Technology Stack**: Python, boto3

**Key Classes**:

```python
class JobOrchestrator:
    """Orchestrates concurrent job execution on EKS and AWS Batch."""

    def __init__(self, eks_cluster: str, batch_job_queue: str):
        """
        Initialize orchestrator.

        Args:
            eks_cluster: EKS cluster name
            batch_job_queue: AWS Batch job queue name
        """

    def submit_spark_jobs(self, count: int) -> List[JobSubmission]:
        """
        Submit multiple Spark jobs to EKS.

        Args:
            count: Number of jobs to submit

        Returns:
            List of job submissions with timestamps
        """

    def submit_batch_jobs(self, count: int) -> List[JobSubmission]:
        """
        Submit multiple Polars jobs to AWS Batch.

        Args:
            count: Number of jobs to submit

        Returns:
            List of job submissions with timestamps
        """

    def monitor_jobs(self, submissions: List[JobSubmission]) -> List[JobMetrics]:
        """
        Monitor job execution and collect metrics.

        Args:
            submissions: List of submitted jobs

        Returns:
            List of job metrics including startup latency
        """

@dataclass
class JobSubmission:
    """Represents a submitted job."""
    job_id: str
    job_type: str  # 'spark' or 'polars'
    created_at: datetime

@dataclass
class JobMetrics:
    """Metrics for a completed job."""
    job_id: str
    job_type: str
    created_at: datetime
    started_at: datetime
    completed_at: datetime
    startup_latency_seconds: float
    execution_time_seconds: float
    peak_memory_mb: int
```

**Orchestration Flow**:
1. Submit 10 Spark jobs to EKS via Kubernetes API
2. Submit 10 Polars jobs to AWS Batch via boto3
3. Poll job status every 5 seconds
4. Record timestamps: created, started, completed
5. Calculate startup latency: started - created
6. Aggregate metrics across all jobs

### Component 5: Analysis Dashboard

**Purpose**: Parse metrics and generate comparison reports with cost analysis.

**Technology Stack**: Python, pandas, boto3

**Key Classes**:

```python
class MetricsAnalyzer:
    """Analyzes benchmark metrics and generates reports."""

    def __init__(self, s3_metrics_path: str):
        """
        Initialize analyzer.

        Args:
            s3_metrics_path: S3 path containing metrics JSON files
        """

    def load_metrics(self) -> pd.DataFrame:
        """Load all metrics from S3 into DataFrame."""

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate mean, median, p95 for all metrics."""

    def calculate_costs(self, pricing: PricingConfig) -> Dict[str, float]:
        """
        Calculate costs based on AWS pricing.

        Args:
            pricing: AWS pricing configuration

        Returns:
            Cost breakdown for each approach
        """

    def generate_markdown_report(self, output_path: str) -> None:
        """Generate Markdown comparison table."""

    def generate_cost_comparison(self, output_path: str) -> None:
        """Generate cost analysis report."""

@dataclass
class PricingConfig:
    """AWS pricing configuration."""
    eks_control_plane_hourly: float = 0.10
    eks_node_vcpu_hourly: float = 0.0416  # m5.xlarge
    batch_fargate_vcpu_hourly: float = 0.04048
    batch_fargate_memory_gb_hourly: float = 0.004445
    s3_request_per_1000: float = 0.0004
```

**Report Format**:

```markdown
# Benchmark Comparison Report

## Performance Metrics

| Metric | PySpark (EKS) | Polars (Batch) | Winner |
|--------|---------------|----------------|--------|
| Execution Time (mean) | 245s | 187s | Polars |
| Startup Latency (mean) | 45s | 8s | Polars |
| Peak Memory (mean) | 12GB | 8GB | Polars |
| Bytes Read | 10.2GB | 10.2GB | Tie |

## Cost Analysis

| Component | PySpark (EKS) | Polars (Batch) |
|-----------|---------------|----------------|
| Compute Cost | $2.45 | $0.87 |
| S3 Requests | $0.02 | $0.02 |
| **Total** | **$2.47** | **$0.89** |
| **Cost per GB** | **$0.242** | **$0.087** |

## Startup Latency Analysis

**PySpark on EKS**:
- Mean: 45s
- Median: 43s
- P95: 62s

**Polars on AWS Batch**:
- Mean: 8s
- Median: 7s
- P95: 12s

**Conclusion**: AWS Batch has 5.6x faster startup time.
```

## Data Models

### TPC-H Schema

The system uses standard TPC-H schema with 8 tables:

**Customer** (150K rows at SF=10):
- c_custkey (PK)
- c_name, c_address, c_nationkey (FK), c_phone
- c_acctbal, c_mktsegment, c_comment

**Orders** (1.5M rows at SF=10):
- o_orderkey (PK)
- o_custkey (FK), o_orderstatus, o_totalprice
- o_orderdate, o_orderpriority, o_clerk, o_shippriority, o_comment

**Lineitem** (6M rows at SF=10, **partitioned by l_shipdate**):
- l_orderkey (FK), l_partkey (FK), l_suppkey (FK), l_linenumber (PK)
- l_quantity, l_extendedprice, l_discount, l_tax
- l_returnflag, l_linestatus, l_shipdate, l_commitdate, l_receiptdate
- l_shipinstruct, l_shipmode, l_comment

**Part** (200K rows at SF=10):
- p_partkey (PK)
- p_name, p_mfgr, p_brand, p_type, p_size, p_container
- p_retailprice, p_comment

**Supplier** (10K rows at SF=10):
- s_suppkey (PK)
- s_name, s_address, s_nationkey (FK), s_phone
- s_acctbal, s_comment

**Partsupp** (800K rows at SF=10):
- ps_partkey (FK), ps_suppkey (FK) (composite PK)
- ps_availqty, ps_supplycost, ps_comment

**Nation** (25 rows):
- n_nationkey (PK)
- n_name, n_regionkey (FK), n_comment

**Region** (5 rows):
- r_regionkey (PK)
- r_name, r_comment

### Metrics Data Model

```python
@dataclass
class JobMetrics:
    """Complete metrics for a single job execution."""
    job_id: str
    job_type: str  # 'spark' or 'polars'
    scale_factor: int  # 10 or 100

    # Timestamps
    created_at: datetime
    started_at: datetime
    completed_at: datetime

    # Performance
    startup_latency_seconds: float
    execution_time_seconds: float
    peak_memory_mb: int

    # I/O
    bytes_read: int
    bytes_written: int
    s3_requests: int

    # Resources
    vcpu_count: int
    memory_gb: int

    # Cost (calculated)
    compute_cost_usd: float
    s3_cost_usd: float
    total_cost_usd: float
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: TPC-H Table Generation Completeness

*For any* TPC-H scale factor, generating data should produce all 8 standard TPC-H tables (customer, lineitem, nation, orders, part, partsupp, region, supplier) with schemas matching the TPC-H specification.

**Validates: Requirements 1.1**

### Property 2: Parquet Output to S3

*For any* generated TPC-H table, the output should be valid Parquet files stored in S3 at the specified bucket and prefix.

**Validates: Requirements 1.2**

### Property 3: Lineitem Partitioning Structure

*For any* generated lineitem table, the S3 structure should follow Hive-style partitioning with year=YYYY/month=MM directories extracted from l_shipdate.

**Validates: Requirements 1.3, 9.1, 9.3**

### Property 4: Scale Factor Support

*For any* scale factor configuration (10 or 100), the generated dataset size should be approximately scale_factor × 1GB for the complete TPC-H dataset.

**Validates: Requirements 1.4**

### Property 5: Generation Progress Logging

*For any* table generation operation, the system should emit log messages indicating progress and completion time.

**Validates: Requirements 1.5**

### Property 6: Query Result Equivalence

*For any* TPC-H query execution, both PySpark and Polars implementations should produce identical results (same rows, same aggregations) when given the same input data.

**Validates: Requirements 2.2**

### Property 7: Complete Metrics Collection

*For any* job execution (Spark or Polars), the system should record all required metrics: startup time, execution time, peak memory, bytes read, and bytes written.

**Validates: Requirements 2.3, 3.6, 8.1, 8.2, 8.3, 8.4**

### Property 8: Metrics Persistence

*For any* completed job, metrics should be written to S3 as a valid JSON file with all required fields populated.

**Validates: Requirements 8.5**

### Property 9: Predicate Pushdown Efficiency

*For any* query with filter predicates, DuckDB should read fewer bytes from S3 compared to reading all data and then filtering in memory.

**Validates: Requirements 3.2, 9.5**

### Property 10: Projection Pushdown Efficiency

*For any* query selecting specific columns, DuckDB should read fewer bytes from S3 compared to SELECT * followed by column selection.

**Validates: Requirements 3.3**

### Property 11: Partition Pruning Efficiency

*For any* query filtering by date on the lineitem table, both implementations should read only the relevant partitions (not all partitions).

**Validates: Requirements 9.4**

### Property 12: Concurrent Job Submission

*For any* orchestration run, the system should successfully submit exactly 10 Spark jobs and exactly 10 Polars jobs.

**Validates: Requirements 4.1, 4.2**

### Property 13: Timestamp Recording

*For any* submitted job, the system should record both "Job Created" and "Job Started" timestamps.

**Validates: Requirements 4.3**

### Property 14: Startup Latency Calculation

*For any* job with recorded timestamps, the startup latency should be calculated as (started_at - created_at) and should be a non-negative value.

**Validates: Requirements 4.4**

### Property 15: Complete Metrics Collection from All Jobs

*For any* orchestration run with 20 jobs (10 Spark + 10 Polars), the system should collect execution metrics from all 20 jobs.

**Validates: Requirements 4.5**

### Property 16: Metrics Extraction from Logs

*For any* set of job logs, the analysis system should successfully extract execution time, memory usage, and startup latency for each job.

**Validates: Requirements 5.1**

### Property 17: Markdown Report Generation

*For any* completed benchmark run, the system should generate a Markdown file containing a comparison table with metrics for both Spark and Polars.

**Validates: Requirements 5.2**

### Property 18: Cost Calculation Accuracy

*For any* job execution, the calculated cost should use the correct AWS pricing formulas: (vCPU × hours × vCPU_rate) + (memory_GB × hours × memory_rate) for Batch, and (node_count × hours × node_rate) + control_plane_cost for EKS.

**Validates: Requirements 5.3**

### Property 19: Cost Metrics in Report

*For any* generated report, it should include both cost-per-GB-processed and total cost for each approach.

**Validates: Requirements 5.4**

### Property 20: Startup Latency Comparison

*For any* generated report, it should include a comparison of startup latency between EKS and Batch approaches.

**Validates: Requirements 5.5**

### Property 21: Type Hint Coverage

*For any* Python function in the codebase, it should have type hints for all parameters and return values.

**Validates: Requirements 6.1**

### Property 22: Exception Handling Coverage

*For any* external operation (S3 access, API calls, file I/O), the code should include try/except blocks with appropriate error logging.

**Validates: Requirements 6.3**

### Property 23: Docstring Coverage

*For any* public function or class, it should have a docstring describing its purpose, parameters, and return value.

**Validates: Requirements 6.4**

### Property 24: Environment Variable Configuration

*For any* AWS resource access (S3 buckets, EKS cluster, Batch queue), the configuration should come from environment variables, not hardcoded values.

**Validates: Requirements 6.5, 7.1, 7.2, 7.3, 7.4**

### Property 25: Parquet Compression

*For any* generated Parquet file, it should use either Snappy or Zstd compression (not uncompressed).

**Validates: Requirements 9.2**

### Property 26: Summary Report Generation

*For any* completed benchmark run, the system should generate a summary report with key findings and recommendations.

**Validates: Requirements 10.4**

### Property 27: Debug Logging Control

*For any* execution, setting the DEBUG environment variable to "true" should enable verbose logging, while any other value should use standard logging.

**Validates: Requirements 10.5**

## Error Handling

### Error Categories

1. **Data Generation Errors**:
   - DuckDB TPC-H extension not available
   - S3 write permissions denied
   - Insufficient disk space for temporary files
   - Invalid scale factor specified

2. **Job Execution Errors**:
   - S3 read permissions denied
   - Out of memory during processing
   - Invalid query syntax
   - Missing input tables

3. **Orchestration Errors**:
   - EKS cluster not accessible
   - AWS Batch queue not found
   - Job submission rate limits exceeded
   - Authentication failures

4. **Analysis Errors**:
   - Metrics files not found in S3
   - Invalid JSON format in metrics
   - Missing required metrics fields
   - Cost calculation errors

### Error Handling Strategy

**Retry Logic**:
- S3 operations: Retry up to 3 times with exponential backoff
- Job submissions: Retry up to 2 times with 5-second delay
- API calls: Use boto3 default retry configuration

**Graceful Degradation**:
- If some jobs fail, continue with successful jobs for analysis
- If metrics are incomplete, report available metrics with warnings
- If cost calculation fails, report performance metrics only

**Error Logging**:
- All errors logged to CloudWatch Logs with full stack traces
- Critical errors also written to S3 for post-mortem analysis
- User-friendly error messages for common issues

**Validation**:
- Validate environment variables at startup
- Validate S3 paths before job submission
- Validate metrics JSON schema before analysis

## Testing Strategy

This POC uses a **dual testing approach** combining unit tests for specific scenarios and property-based tests for comprehensive coverage.

### Unit Testing

Unit tests focus on:
- **Specific examples**: Verify TPC-H Query 3 produces expected results for known input
- **Edge cases**: Empty datasets, single-row tables, null values
- **Error conditions**: Missing S3 buckets, invalid credentials, malformed data
- **Integration points**: DuckDB to Polars handoff, boto3 API calls

**Example Unit Tests**:
```python
def test_tpch_generator_creates_customer_table():
    """Verify customer table is generated with correct schema."""

def test_spark_job_handles_missing_table():
    """Verify Spark job raises appropriate error for missing table."""

def test_polars_streaming_mode_enabled():
    """Verify Polars uses streaming mode for large datasets."""

def test_cost_calculator_handles_zero_duration():
    """Verify cost calculation handles edge case of zero execution time."""
```

### Property-Based Testing

Property tests verify universal properties across randomized inputs using **Hypothesis** (Python property-based testing library).

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number
- Tag format: `# Feature: pythonic-etl-benchmark, Property N: [property text]`

**Example Property Tests**:

```python
from hypothesis import given, strategies as st

@given(scale_factor=st.integers(min_value=1, max_value=100))
def test_property_4_scale_factor_support(scale_factor):
    """
    Feature: pythonic-etl-benchmark, Property 4: Scale Factor Support

    For any scale factor, generated dataset size should be approximately
    scale_factor × 1GB.
    """
    generator = TPCHGenerator(scale_factor, bucket, prefix)
    generator.generate_all_tables()

    total_size = get_s3_total_size(bucket, prefix)
    expected_size = scale_factor * 1e9  # 1GB in bytes

    # Allow 20% variance due to compression and data characteristics
    assert 0.8 * expected_size <= total_size <= 1.2 * expected_size

@given(
    filter_date=st.dates(min_value=date(1992, 1, 1), max_value=date(1998, 12, 31))
)
def test_property_9_predicate_pushdown_efficiency(filter_date):
    """
    Feature: pythonic-etl-benchmark, Property 9: Predicate Pushdown Efficiency

    For any filter date, DuckDB should read fewer bytes with predicate pushdown
    than reading all data then filtering.
    """
    # Query with pushdown
    bytes_with_pushdown = measure_bytes_read(
        f"SELECT * FROM lineitem WHERE l_shipdate > '{filter_date}'"
    )

    # Query without pushdown (read all, then filter)
    bytes_without_pushdown = measure_bytes_read(
        "SELECT * FROM lineitem"
    )

    assert bytes_with_pushdown < bytes_without_pushdown

@given(
    columns=st.lists(
        st.sampled_from(['l_orderkey', 'l_extendedprice', 'l_discount', 'l_quantity']),
        min_size=1,
        max_size=4,
        unique=True
    )
)
def test_property_10_projection_pushdown_efficiency(columns):
    """
    Feature: pythonic-etl-benchmark, Property 10: Projection Pushdown Efficiency

    For any column selection, DuckDB should read fewer bytes than SELECT *.
    """
    column_list = ', '.join(columns)

    bytes_with_projection = measure_bytes_read(
        f"SELECT {column_list} FROM lineitem LIMIT 1000"
    )

    bytes_without_projection = measure_bytes_read(
        "SELECT * FROM lineitem LIMIT 1000"
    )

    assert bytes_with_projection <= bytes_without_projection

@given(
    job_count=st.integers(min_value=1, max_value=20)
)
def test_property_12_concurrent_job_submission(job_count):
    """
    Feature: pythonic-etl-benchmark, Property 12: Concurrent Job Submission

    For any number of jobs, orchestrator should successfully submit all jobs.
    """
    orchestrator = JobOrchestrator(eks_cluster, batch_queue)

    spark_submissions = orchestrator.submit_spark_jobs(job_count)
    batch_submissions = orchestrator.submit_batch_jobs(job_count)

    assert len(spark_submissions) == job_count
    assert len(batch_submissions) == job_count
    assert all(s.job_id for s in spark_submissions)
    assert all(s.job_id for s in batch_submissions)
```

### Testing Balance

- **Unit tests**: ~30 tests covering specific examples and edge cases
- **Property tests**: ~15 tests covering universal properties with 100+ iterations each
- **Integration tests**: ~5 tests covering end-to-end workflows

This balance ensures:
- Specific scenarios are validated (unit tests)
- General correctness is verified across many inputs (property tests)
- Real-world workflows are tested (integration tests)

### Test Execution

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/ -m "not property"

# Run only property tests (with warning about long runtime)
pytest tests/ -m property

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Continuous Integration

- All tests run on every commit
- Property tests run with reduced iterations (10) in CI for speed
- Full property tests (100 iterations) run nightly
- Test results published to S3 for tracking
