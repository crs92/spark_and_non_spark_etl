#!/bin/bash
# User data script for Polars ETL EC2 instance
# This script runs on first boot to set up the environment

set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== Starting EC2 instance setup for Polars ETL ==="
echo "Timestamp: $(date)"

# Update system packages
echo "Updating system packages..."
dnf update -y

# Install required system packages
echo "Installing system dependencies..."
dnf install -y \
    git \
    wget \
    curl \
    tar \
    gzip \
    gcc \
    gcc-c++ \
    make \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    zlib-devel \
    amazon-cloudwatch-agent

# Install Python 3.12
echo "Installing Python 3.12..."
dnf install -y python3.12 python3.12-pip python3.12-devel

# Set Python 3.12 as default
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
alternatives --set python3 /usr/bin/python3.12

# Verify Python installation
python3 --version

# Install uv (fast Python package installer)
echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.cargo/bin:$PATH"
echo 'export PATH="/root/.cargo/bin:$PATH"' >> /root/.bashrc

# Create application directory
echo "Creating application directory..."
mkdir -p /opt/etl-benchmark
cd /opt/etl-benchmark

# Clone repository (if git_repo_url is provided and not default)
%{ if git_repo_url != "https://github.com/yourusername/etl-benchmark.git" }
echo "Cloning repository from ${git_repo_url}..."
git clone -b ${git_branch} ${git_repo_url} .
%{ else }
echo "No valid git repository URL provided, skipping clone..."
echo "You'll need to manually upload your code to /opt/etl-benchmark"
%{ endif }

# Create Python virtual environment with uv
echo "Creating Python virtual environment..."
/root/.cargo/bin/uv venv /opt/etl-benchmark/.venv
source /opt/etl-benchmark/.venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
/root/.cargo/bin/uv pip install \
    polars \
    s3fs \
    boto3 \
    pyarrow \
    fastparquet \
    psutil \
    python-json-logger

# Configure AWS CLI
echo "Configuring AWS CLI..."
aws configure set region ${aws_region}
aws configure set output json

# Configure CloudWatch agent
echo "Configuring CloudWatch agent..."
cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<EOF
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/user-data.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/user-data",
            "retention_in_days": 7
          },
          {
            "file_path": "/opt/etl-benchmark/logs/etl.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/etl",
            "retention_in_days": 7
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "ETLBenchmark/EC2",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          {
            "name": "cpu_usage_idle",
            "rename": "CPU_IDLE",
            "unit": "Percent"
          },
          {
            "name": "cpu_usage_iowait",
            "rename": "CPU_IOWAIT",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60,
        "totalcpu": false
      },
      "disk": {
        "measurement": [
          {
            "name": "used_percent",
            "rename": "DISK_USED",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "MEM_USED",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60
      },
      "netstat": {
        "measurement": [
          {
            "name": "tcp_established",
            "rename": "TCP_ESTABLISHED",
            "unit": "Count"
          }
        ],
        "metrics_collection_interval": 60
      }
    }
  }
}
EOF

# Start CloudWatch agent
echo "Starting CloudWatch agent..."
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

# Create logs directory
mkdir -p /opt/etl-benchmark/logs

# Create systemd service for ETL execution
echo "Creating systemd service..."
cat > /etc/systemd/system/polars-etl.service <<EOF
[Unit]
Description=Polars ETL Benchmark Service
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/etl-benchmark
Environment="PATH=/opt/etl-benchmark/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/etl-benchmark"
Environment="S3_BUCKET=${s3_bucket_name}"
Environment="AWS_REGION=${aws_region}"
ExecStart=/opt/etl-benchmark/.venv/bin/python3 src/etl/polars_etl_nyc_taxi.py
StandardOutput=append:/opt/etl-benchmark/logs/etl.log
StandardError=append:/opt/etl-benchmark/logs/etl.log
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Create a helper script for running benchmarks
cat > /opt/etl-benchmark/run_benchmark.sh <<'EOF'
#!/bin/bash
# Helper script to run Polars ETL benchmark

set -e

# Activate virtual environment
source /opt/etl-benchmark/.venv/bin/activate

# Parse arguments
DATA_SIZE=$${1:-small}
OUTPUT_PREFIX=$${2:-polars}

echo "Running Polars ETL benchmark..."
echo "Data size: $DATA_SIZE"
echo "Output prefix: $OUTPUT_PREFIX"
echo "Timestamp: $(date)"

# Run the ETL
python3 /opt/etl-benchmark/src/etl/polars_etl_nyc_taxi.py \
    --data-size "$DATA_SIZE" \
    --output-prefix "$OUTPUT_PREFIX"

echo "Benchmark complete!"
EOF

chmod +x /opt/etl-benchmark/run_benchmark.sh

# Test S3 access
echo "Testing S3 access..."
aws s3 ls s3://nyc-tlc/trip\ data/ --max-items 5 || echo "Warning: Could not list NYC TLC bucket"
aws s3 ls s3://${s3_bucket_name}/ || echo "Warning: Could not list benchmark bucket"

# Create completion marker
echo "Setup completed at $(date)" > /opt/etl-benchmark/setup_complete.txt

echo "=== EC2 instance setup complete ==="
echo "Instance is ready for Polars ETL benchmarking"
echo "To run a benchmark: /opt/etl-benchmark/run_benchmark.sh <data_size>"
echo "Example: /opt/etl-benchmark/run_benchmark.sh small"
