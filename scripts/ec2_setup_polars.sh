#!/bin/bash
# Standalone EC2 setup script for Polars ETL
# This script can be run manually on an EC2 instance or used as user data
#
# Usage:
#   sudo bash ec2_setup_polars.sh [S3_BUCKET_NAME] [AWS_REGION] [GIT_REPO_URL] [GIT_BRANCH]
#
# Example:
#   sudo bash ec2_setup_polars.sh etl-benchmark-data-123456789 us-east-1 https://github.com/user/repo.git main

set -e

# Configuration (can be overridden by arguments)
S3_BUCKET_NAME="${1:-etl-benchmark-data}"
AWS_REGION="${2:-us-east-1}"
GIT_REPO_URL="${3:-https://github.com/yourusername/etl-benchmark.git}"
GIT_BRANCH="${4:-main}"
CLOUDWATCH_LOG_GROUP="/aws/ec2/polars-etl"

# Log all output
LOG_FILE="/var/log/polars-setup.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "=========================================="
echo "Polars ETL EC2 Setup Script"
echo "=========================================="
echo "Timestamp: $(date)"
echo "S3 Bucket: $S3_BUCKET_NAME"
echo "AWS Region: $AWS_REGION"
echo "Git Repo: $GIT_REPO_URL"
echo "Git Branch: $GIT_BRANCH"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "ERROR: This script must be run as root (use sudo)"
  exit 1
fi

# Update system packages
echo "[1/10] Updating system packages..."
dnf update -y

# Install required system packages
echo "[2/10] Installing system dependencies..."
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
    amazon-cloudwatch-agent \
    htop \
    iotop \
    sysstat

# Install Python 3.12
echo "[3/10] Installing Python 3.12..."
dnf install -y python3.12 python3.12-pip python3.12-devel

# Set Python 3.12 as default
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
alternatives --set python3 /usr/bin/python3.12

# Verify Python installation
echo "Python version: $(python3 --version)"

# Install uv (fast Python package installer)
echo "[4/10] Installing uv package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.cargo/bin:$PATH"

# Add uv to PATH for all users
echo 'export PATH="/root/.cargo/bin:$PATH"' >> /root/.bashrc
echo 'export PATH="/root/.cargo/bin:$PATH"' >> /etc/profile.d/uv.sh

# Verify uv installation
/root/.cargo/bin/uv --version

# Create application directory
echo "[5/10] Setting up application directory..."
mkdir -p /opt/etl-benchmark
cd /opt/etl-benchmark

# Clone repository if URL is valid
if [ "$GIT_REPO_URL" != "https://github.com/yourusername/etl-benchmark.git" ]; then
    echo "Cloning repository from $GIT_REPO_URL..."
    if git clone -b "$GIT_BRANCH" "$GIT_REPO_URL" .; then
        echo "Repository cloned successfully"
    else
        echo "WARNING: Failed to clone repository. You'll need to manually upload code."
    fi
else
    echo "No valid git repository URL provided."
    echo "Please manually upload your code to /opt/etl-benchmark"
fi

# Create Python virtual environment with uv
echo "[6/10] Creating Python virtual environment..."
/root/.cargo/bin/uv venv /opt/etl-benchmark/.venv

# Activate virtual environment
source /opt/etl-benchmark/.venv/bin/activate

# Install Python dependencies
echo "[7/10] Installing Python dependencies..."
/root/.cargo/bin/uv pip install \
    polars \
    s3fs \
    boto3 \
    pyarrow \
    fastparquet \
    psutil \
    python-json-logger \
    numpy \
    pandas

# Configure AWS CLI
echo "[8/10] Configuring AWS CLI..."
aws configure set region "$AWS_REGION"
aws configure set output json

# Configure CloudWatch agent
echo "[9/10] Configuring CloudWatch agent..."
mkdir -p /opt/aws/amazon-cloudwatch-agent/etc

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
            "file_path": "/var/log/polars-setup.log",
            "log_group_name": "$CLOUDWATCH_LOG_GROUP",
            "log_stream_name": "{instance_id}/setup",
            "retention_in_days": 7
          },
          {
            "file_path": "/opt/etl-benchmark/logs/etl.log",
            "log_group_name": "$CLOUDWATCH_LOG_GROUP",
            "log_stream_name": "{instance_id}/etl",
            "retention_in_days": 7
          },
          {
            "file_path": "/opt/etl-benchmark/logs/benchmark.log",
            "log_group_name": "$CLOUDWATCH_LOG_GROUP",
            "log_stream_name": "{instance_id}/benchmark",
            "retention_in_days": 7
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "ETLBenchmark/EC2/Polars",
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
          },
          {
            "name": "cpu_usage_system",
            "rename": "CPU_SYSTEM",
            "unit": "Percent"
          },
          {
            "name": "cpu_usage_user",
            "rename": "CPU_USER",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      },
      "disk": {
        "measurement": [
          {
            "name": "used_percent",
            "rename": "DISK_USED_PERCENT",
            "unit": "Percent"
          },
          {
            "name": "free",
            "rename": "DISK_FREE",
            "unit": "Gigabytes"
          }
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "diskio": {
        "measurement": [
          {
            "name": "io_time",
            "rename": "DISK_IO_TIME",
            "unit": "Milliseconds"
          },
          {
            "name": "read_bytes",
            "rename": "DISK_READ_BYTES",
            "unit": "Bytes"
          },
          {
            "name": "write_bytes",
            "rename": "DISK_WRITE_BYTES",
            "unit": "Bytes"
          }
        ],
        "metrics_collection_interval": 60
      },
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "MEM_USED_PERCENT",
            "unit": "Percent"
          },
          {
            "name": "mem_available",
            "rename": "MEM_AVAILABLE",
            "unit": "Megabytes"
          },
          {
            "name": "mem_used",
            "rename": "MEM_USED",
            "unit": "Megabytes"
          }
        ],
        "metrics_collection_interval": 60
      },
      "net": {
        "measurement": [
          {
            "name": "bytes_sent",
            "rename": "NET_BYTES_SENT",
            "unit": "Bytes"
          },
          {
            "name": "bytes_recv",
            "rename": "NET_BYTES_RECV",
            "unit": "Bytes"
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
echo "[10/10] Creating systemd service..."
cat > /etc/systemd/system/polars-etl.service <<EOF
[Unit]
Description=Polars ETL Benchmark Service
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/etl-benchmark
Environment="PATH=/opt/etl-benchmark/.venv/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/etl-benchmark"
Environment="S3_BUCKET=$S3_BUCKET_NAME"
Environment="AWS_REGION=$AWS_REGION"
ExecStart=/opt/etl-benchmark/.venv/bin/python3 src/etl/polars_etl_nyc_taxi.py
StandardOutput=append:/opt/etl-benchmark/logs/etl.log
StandardError=append:/opt/etl-benchmark/logs/etl.log
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Create helper scripts
echo "Creating helper scripts..."

# Benchmark runner script
cat > /opt/etl-benchmark/run_benchmark.sh <<'SCRIPT_EOF'
#!/bin/bash
# Helper script to run Polars ETL benchmark

set -e

# Activate virtual environment
source /opt/etl-benchmark/.venv/bin/activate

# Parse arguments
DATA_SIZE=${1:-small}
OUTPUT_PREFIX=${2:-polars}

echo "=========================================="
echo "Running Polars ETL Benchmark"
echo "=========================================="
echo "Data size: $DATA_SIZE"
echo "Output prefix: $OUTPUT_PREFIX"
echo "Timestamp: $(date)"
echo "=========================================="

# Run the ETL
python3 /opt/etl-benchmark/src/etl/polars_etl_nyc_taxi.py \
    --data-size "$DATA_SIZE" \
    --output-prefix "$OUTPUT_PREFIX"

echo "=========================================="
echo "Benchmark complete!"
echo "=========================================="
SCRIPT_EOF

chmod +x /opt/etl-benchmark/run_benchmark.sh

# System info script
cat > /opt/etl-benchmark/system_info.sh <<'SCRIPT_EOF'
#!/bin/bash
# Display system information

echo "=========================================="
echo "System Information"
echo "=========================================="
echo "Hostname: $(hostname)"
echo "Instance ID: $(ec2-metadata --instance-id | cut -d ' ' -f 2)"
echo "Instance Type: $(ec2-metadata --instance-type | cut -d ' ' -f 2)"
echo "Availability Zone: $(ec2-metadata --availability-zone | cut -d ' ' -f 2)"
echo ""
echo "CPU Info:"
lscpu | grep -E "Model name|CPU\(s\)|Thread|Core"
echo ""
echo "Memory Info:"
free -h
echo ""
echo "Disk Info:"
df -h /
echo ""
echo "Python Version:"
python3 --version
echo ""
echo "Polars Version:"
source /opt/etl-benchmark/.venv/bin/activate
python3 -c "import polars; print(f'Polars {polars.__version__}')"
echo "=========================================="
SCRIPT_EOF

chmod +x /opt/etl-benchmark/system_info.sh

# Test S3 access
echo "Testing S3 access..."
echo "Testing NYC TLC bucket (public)..."
aws s3 ls s3://nyc-tlc/trip\ data/ --max-items 5 || echo "WARNING: Could not list NYC TLC bucket"

echo "Testing benchmark bucket..."
aws s3 ls s3://$S3_BUCKET_NAME/ || echo "WARNING: Could not list benchmark bucket (may not exist yet)"

# Create completion marker
cat > /opt/etl-benchmark/setup_complete.txt <<EOF
Setup completed at: $(date)
S3 Bucket: $S3_BUCKET_NAME
AWS Region: $AWS_REGION
Git Repo: $GIT_REPO_URL
Git Branch: $GIT_BRANCH
Python Version: $(python3 --version)
EOF

# Display system info
/opt/etl-benchmark/system_info.sh

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Verify setup: cat /opt/etl-benchmark/setup_complete.txt"
echo "  2. View system info: /opt/etl-benchmark/system_info.sh"
echo "  3. Run benchmark: /opt/etl-benchmark/run_benchmark.sh <data_size>"
echo "     Example: /opt/etl-benchmark/run_benchmark.sh small"
echo ""
echo "Available data sizes: tiny, small, medium, large, xlarge"
echo ""
echo "Logs location: /opt/etl-benchmark/logs/"
echo "CloudWatch log group: $CLOUDWATCH_LOG_GROUP"
echo ""
echo "=========================================="
