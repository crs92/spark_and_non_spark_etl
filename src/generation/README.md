# TPC-H Data Generation

Complete guide for generating TPC-H benchmark data locally or on EC2.

## Overview

Two generation methods available:

1. **Local Generation** (`generate_tpch_data_fast.py`) - Fast local generation using tpchgen-rs
2. **EC2 Generation** (`generate_on_ec2.py`) - Generate on EC2 for large scale factors with fast S3 upload

## Quick Start

### Local Generation (Recommended for SF ≤ 10)

```bash
# Install tpchgen-rs (one-time setup)
cargo install tpchgen-cli

# Generate SF 10 locally
python -m src.generation.generate_tpch_data_fast --scale-factor 10
```

**Pros:**
- Fast for small scale factors (SF 1-10)
- No AWS costs
- Immediate results (~6 seconds generation)

**Cons:**
- Requires local memory (SF 10 = ~2GB)
- Slow S3 upload on slow networks
- Limited by local resources

### EC2 Generation (Recommended for SF ≥ 10)

```bash
# Generate SF 100 on EC2
python -m src.generation.generate_on_ec2 --scale-factor 100
```

**Pros:**
- Fast S3 upload (10+ Gbps internal AWS network)
- No local memory limits
- Handles large scale factors (SF 100 = 38GB)

**Cons:**
- AWS costs (~$0.20 for SF 100)
- Takes ~6 minutes (includes Rust compilation)

---

## Local Generation Details

### Prerequisites

1. **Install Rust and tpchgen-cli:**
   ```bash
   # Install Rust
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env

   # Install tpchgen-cli
   cargo install tpchgen-cli
   ```

2. **Python dependencies:**
   ```bash
   pip install boto3 python-dotenv
   ```

3. **AWS credentials in `.env`:**
   ```
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_SESSION_TOKEN=...
   AWS_REGION=eu-central-1
   S3_BUCKET_NAME=your-bucket
   ```

### Usage

```bash
# Generate and upload to S3
python -m src.generation.generate_tpch_data_fast --scale-factor 10

# Generate only (no S3 upload)
python -m src.generation.generate_tpch_data_fast --scale-factor 10 --local-only

# Custom output directory
python -m src.generation.generate_tpch_data_fast --scale-factor 10 --output-dir /tmp/tpch
```

### How It Works

1. Uses `tpchgen_wrapper.py` to call tpchgen-cli binary
2. Generates Parquet files in `data/tpch-sf{scale_factor}/`
3. Uploads to S3 at `s3://{bucket}/tpch-sf{scale_factor}/`

### Performance

| Scale Factor | Data Size | Generation Time | Upload Time (50 Mbps) |
|--------------|-----------|-----------------|----------------------|
| SF 1         | 360 MB    | ~1 second       | ~1 minute            |
| SF 10        | 3.6 GB    | ~6 seconds      | ~10 minutes          |
| SF 100       | 38 GB     | ~60 seconds     | ~100 minutes         |

---

## EC2 Generation Details

### Prerequisites

1. **AWS credentials in `.env`:**
   ```
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_SESSION_TOKEN=...
   AWS_REGION=eu-central-1
   S3_BUCKET_NAME=your-bucket
   ```

2. **Python dependencies:**
   ```bash
   pip install boto3 python-dotenv
   ```

### Usage

```bash
# Generate SF 100 on EC2
python -m src.generation.generate_on_ec2 --scale-factor 100

# Custom bucket
python -m src.generation.generate_on_ec2 --scale-factor 100 --bucket my-bucket

# Different region
python -m src.generation.generate_on_ec2 --scale-factor 100 --region us-east-1
```

### How It Works

1. **Launches EC2 instance** (c6i.2xlarge with 50GB EBS)
2. **Creates IAM role** with S3 and SSM permissions
3. **Installs Rust + tpchgen-cli** (~4 minutes via cargo)
4. **Generates TPC-H data** (~6 seconds for SF 10, ~60s for SF 100)
5. **Uploads to S3** (~30 seconds via 10+ Gbps internal network)
6. **Terminates instance** (automatic cleanup)

### Performance

| Scale Factor | Data Size | Total Time | Cost (c6i.2xlarge) |
|--------------|-----------|------------|--------------------|
| SF 1         | 360 MB    | ~5 min     | $0.04              |
| SF 10        | 3.6 GB    | ~5 min     | $0.04              |
| SF 100       | 38 GB     | ~6 min     | $0.20              |

### Instance Type Choice

The script uses **c6i.2xlarge** (8 vCPU, 16GB RAM) because:
- Faster CPU = Faster Rust compilation (~4 min vs ~10 min on t3.medium)
- More memory for large scale factors
- Still cost-effective (~$0.17/hour)

---

## Architecture

### File Structure

```
src/generation/
├── README.md                      # This file
├── generate_tpch_data_fast.py     # Local generation script
├── generate_on_ec2.py             # EC2 generation script
├── tpchgen_wrapper.py             # Python wrapper for tpchgen-cli
└── __init__.py
```

### tpchgen-rs

Both methods use [tpchgen-rs](https://github.com/clflushopt/tpchgen-rs), a fast Rust implementation of TPC-H data generation.

**Why tpchgen-rs?**
- 20x faster than DuckDB's dbgen
- Constant memory usage (~2GB regardless of scale factor)
- Native Parquet output
- No compilation needed (uses pre-built binary locally)

**Performance comparison (SF 10):**
- DuckDB dbgen: 30+ minutes, 10-12GB memory
- tpchgen-rs: 6 seconds, 2GB memory

---

## Troubleshooting

### Local Generation Issues

**Issue: `tpchgen-cli: command not found`**

Solution:
```bash
# Ensure Rust is installed
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install tpchgen-cli
cargo install tpchgen-cli

# Verify installation
tpchgen-cli --version
```

**Issue: Slow S3 upload**

Solution: Use EC2 generation for large scale factors (SF ≥ 10)

### EC2 Generation Issues

**Issue: IAM permissions error**

Solution: The script automatically creates IAM roles. If it fails, ensure your AWS credentials have IAM permissions:
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `iam:CreateInstanceProfile`

**Issue: Session token expired**

Solution: Refresh AWS credentials in `.env` file:
```bash
# Get new credentials from AWS console or CLI
# Update .env file with new values
```

**Issue: Instance still running**

Check and terminate manually:
```bash
python3 << 'EOF'
import boto3
from dotenv import load_dotenv
load_dotenv('.env')

ec2 = boto3.client('ec2', region_name='eu-central-1')
response = ec2.describe_instances(
    Filters=[
        {'Name': 'tag:Name', 'Values': ['tpch-sf*']},
        {'Name': 'instance-state-name', 'Values': ['running']}
    ]
)

for r in response['Reservations']:
    for i in r['Instances']:
        instance_id = i['InstanceId']
        print(f"Terminating: {instance_id}")
        ec2.terminate_instances(InstanceIds=[instance_id])
EOF
```

### Verify S3 Data

```bash
python3 << 'EOF'
import boto3
from dotenv import load_dotenv
load_dotenv('.env')

s3 = boto3.client('s3', region_name='eu-central-1')
response = s3.list_objects_v2(Bucket='your-bucket', Prefix='tpch-sf10/')

if 'Contents' in response:
    total = sum(obj['Size'] for obj in response['Contents'])
    print(f"✅ {len(response['Contents'])} files, {total/1024/1024:.1f} MB")
    for obj in response['Contents']:
        print(f"  {obj['Key']}")
else:
    print("❌ No files found")
EOF
```

---

## Decision Guide

**Use Local Generation when:**
- Scale factor ≤ 10
- You have good network (>50 Mbps upload)
- You have enough memory (SF 10 = ~2GB)
- You want immediate results

**Use EC2 Generation when:**
- Scale factor ≥ 10
- Slow local network
- Limited local memory
- You need fast S3 upload

---

## Cost Analysis

### Local Generation
- **Compute**: Free (uses local machine)
- **S3 Upload**: Data transfer costs (varies by region)
- **Total**: ~$0.01 per GB uploaded

### EC2 Generation
- **Compute**: c6i.2xlarge @ $0.17/hour
- **S3 Upload**: Free (internal AWS network)
- **Total**: ~$0.04 for SF 10, ~$0.20 for SF 100

**Recommendation**: For SF ≥ 10, EC2 is more cost-effective due to fast upload.

---

## References

- [tpchgen-rs GitHub](https://github.com/clflushopt/tpchgen-rs)
- [TPC-H Benchmark Specification](http://www.tpc.org/tpch/)
- [AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/)
