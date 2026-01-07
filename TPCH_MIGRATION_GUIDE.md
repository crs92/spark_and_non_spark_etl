# TPC-H Benchmark Migration Guide

This document describes the changes made to adapt the existing NYC Taxi benchmark project for the TPC-H benchmark POC.

## Overview

The project has been strategically pivoted from NYC Taxi data to TPC-H standard benchmark data while preserving existing infrastructure and analysis capabilities.

## Changes Made

### 1. New Directory Structure

Added two new modules to support TPC-H benchmark:

```
src/
├── generation/          # NEW: TPC-H data generation
│   ├── __init__.py
│   └── README.md
├── orchestration/       # NEW: Multi-job orchestration
│   ├── __init__.py
│   └── README.md
├── analysis/           # EXISTING: Cost and performance analysis
├── etl/                # EXISTING: ETL implementations
└── utils/              # ENHANCED: Logging configuration
    ├── __init__.py
    ├── helpers.py
    └── logging_config.py  # NEW
```

### 2. Dependencies Added

Updated `pyproject.toml` to include:
- **boto3**: AWS SDK for Python (EKS, Batch, S3 operations)
- **hypothesis**: Property-based testing framework

Existing dependencies preserved:
- duckdb, polars, pyarrow, pyspark, pytest

### 3. Environment Configuration

Created comprehensive `.env.example` with TPC-H-specific variables:

**Key Configuration Sections:**
- AWS Configuration (credentials, region)
- S3 Configuration (bucket, prefixes)
- EKS Configuration (cluster name, namespace)
- AWS Batch Configuration (job queue, job definition)
- TPC-H Benchmark Configuration (scale factor, concurrent jobs)
- Performance Monitoring (CloudWatch, metrics)
- Cost Analysis (pricing overrides)
- Job Configuration (Spark and Polars settings)

**Required Variables:**
- `S3_BUCKET_NAME`: S3 bucket for TPC-H data and results
- `EKS_CLUSTER_NAME`: EKS cluster for Spark jobs
- `BATCH_JOB_QUEUE`: AWS Batch queue for Polars jobs
- `BATCH_JOB_DEFINITION`: AWS Batch job definition

### 4. Enhanced Logging

Created `src/utils/logging_config.py` with:
- Environment-based log level control (`LOG_LEVEL`)
- Debug mode toggle (`DEBUG=true`)
- Structured logging format
- CloudWatch integration support
- Convenience functions: `get_logger()`, `setup_logging()`

**Usage Example:**
```python
from src.utils import get_logger

logger = get_logger(__name__)
logger.info("Starting TPC-H data generation")
```

## Preserved Infrastructure

The following existing components are **preserved and will be adapted**:

### Analysis Module (`src/analysis/`)
- `cost_calculator.py` - Will be extended for TPC-H cost analysis
- `crossover_analyzer.py` - Will be adapted for TPC-H metrics
- `tco_analyzer.py` - Will be reused for total cost of ownership

### ETL Module (`src/etl/`)
- `timing_decorator.py` - Will be reused for performance tracking
- `nyc_taxi_data_access.py` - Pattern will be adapted for TPC-H data access
- Existing Polars and Spark implementations serve as templates

### Utils Module (`src/utils/`)
- `helpers.py` - Preserved for utility functions
- Enhanced with new `logging_config.py`

## Migration Path

### Phase 1: Data Generation (Task 2)
Implement TPC-H data generator in `src/generation/`

### Phase 2: ETL Implementations (Tasks 4-5)
- Adapt PySpark implementation for TPC-H Query 3
- Adapt Polars/DuckDB implementation with optimizations

### Phase 3: Orchestration (Task 7)
Implement multi-job orchestrator in `src/orchestration/`

### Phase 4: Analysis (Task 8)
Extend existing analysis modules for TPC-H metrics

## Setup Instructions

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS configuration
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   # Or with uv:
   uv pip install -e .
   ```

3. **Configure AWS credentials:**
   ```bash
   # Option 1: Environment variables in .env
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret

   # Option 2: AWS CLI configuration
   aws configure

   # Option 3: IAM roles (recommended for EC2/EKS)
   ```

4. **Verify setup:**
   ```bash
   python -c "from src.utils import get_logger; logger = get_logger('test'); logger.info('Setup complete')"
   ```

## Next Steps

1. Implement TPC-H data generator (Task 2)
2. Set up AWS infrastructure (EKS cluster, Batch queue)
3. Implement PySpark baseline (Task 4)
4. Implement Polars/DuckDB challenger (Task 5)
5. Implement orchestration (Task 7)
6. Extend analysis modules (Task 8)

## Compatibility Notes

- Python 3.10+ required (unchanged)
- All existing NYC Taxi code remains functional
- New TPC-H code is isolated in new modules
- Shared utilities (logging, timing) work for both benchmarks

## Questions?

Refer to:
- `.kiro/specs/pythonic-etl-benchmark/requirements.md` - Full requirements
- `.kiro/specs/pythonic-etl-benchmark/design.md` - Detailed design
- `.kiro/specs/pythonic-etl-benchmark/tasks.md` - Implementation tasks
- `src/generation/README.md` - Data generation module
- `src/orchestration/README.md` - Orchestration module
