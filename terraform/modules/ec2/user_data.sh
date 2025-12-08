#!/bin/bash
# User data script for Polars ETL EC2 instance
# This script runs on first boot to set up Docker and pull the Polars image

set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== Starting EC2 instance setup for Polars ETL (Docker-based) ==="
echo "Timestamp: $(date)"

# Update system packages
echo "Updating system packages..."
dnf update -y

# Install Docker and CloudWatch agent
echo "Installing Docker and CloudWatch agent..."
dnf install -y docker amazon-cloudwatch-agent

# Start and enable Docker
echo "Starting Docker service..."
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group (for non-root access)
usermod -aG docker ec2-user

# Get AWS account ID for ECR
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.${aws_region}.amazonaws.com"
POLARS_IMAGE="$ECR_REGISTRY/polars-etl:latest"

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "ECR Registry: $ECR_REGISTRY"
echo "Polars Image: $POLARS_IMAGE"

# Authenticate Docker with ECR
echo "Authenticating Docker with ECR..."
aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin $ECR_REGISTRY

# Pull Polars Docker image
echo "Pulling Polars Docker image from ECR..."
docker pull $POLARS_IMAGE || echo "Warning: Could not pull Polars image. Make sure it's pushed to ECR with: make ecr-push-polars"

# Configure AWS CLI
echo "Configuring AWS CLI..."
aws configure set region ${aws_region}
aws configure set output json

# Configure CloudWatch agent
echo "Configuring CloudWatch agent..."
mkdir -p /opt/aws/amazon-cloudwatch-agent/etc

cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<CWEOF
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
            "file_path": "/var/log/polars-etl/benchmark.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/benchmark",
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
        "resources": ["*"]
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
      }
    }
  }
}
CWEOF

# Start CloudWatch agent
echo "Starting CloudWatch agent..."
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

# Create logs directory
mkdir -p /var/log/polars-etl

# Create a helper script for running benchmarks with Docker
cat > /usr/local/bin/run-polars-benchmark.sh <<'SCRIPTEOF'
#!/bin/bash
# Helper script to run Polars ETL benchmark in Docker

set -e

# Parse arguments
DATA_SIZE=$${1:-tiny}

# Get ECR image details
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
POLARS_IMAGE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/polars-etl:latest"

echo "=========================================="
echo "Running Polars ETL Benchmark (Docker)"
echo "=========================================="
echo "Data size: $DATA_SIZE"
echo "AWS Region: $AWS_REGION"
echo "Docker Image: $POLARS_IMAGE"
echo "Timestamp: $(date)"
echo "=========================================="

# Get AWS credentials from EC2 instance metadata (IMDSv2)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null)
ROLE_NAME=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>/dev/null)
CREDENTIALS=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE_NAME 2>/dev/null)

# Extract credentials
AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | grep -o '"AccessKeyId" : "[^"]*' | cut -d'"' -f4)
AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | grep -o '"SecretAccessKey" : "[^"]*' | cut -d'"' -f4)
AWS_SESSION_TOKEN=$(echo $CREDENTIALS | grep -o '"Token" : "[^"]*' | cut -d'"' -f4)

# Run the ETL in Docker with AWS credentials from EC2 IAM role
docker run --rm \
    -e AWS_REGION=$AWS_REGION \
    -e AWS_DEFAULT_REGION=$AWS_REGION \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
    -v /var/log/polars-etl:/app/logs \
    $POLARS_IMAGE \
    python -m src.etl.polars_etl_nyc_taxi --size $DATA_SIZE

EXIT_CODE=$?

echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "Benchmark complete!"
else
    echo "Benchmark failed with exit code: $EXIT_CODE"
fi
echo "=========================================="

exit $EXIT_CODE
SCRIPTEOF

chmod +x /usr/local/bin/run-polars-benchmark.sh

# Test Docker
echo "Testing Docker..."
docker --version
docker images

# Test S3 access
echo "Testing S3 access..."
aws s3 ls s3://nyc-tlc/trip\ data/ --max-items 5 || echo "Warning: Could not list NYC TLC bucket"
aws s3 ls s3://${s3_bucket_name}/ || echo "Warning: Could not list benchmark bucket"

# Create completion marker
cat > /var/log/polars-setup-complete.txt <<MARKEREOF
Setup completed at: $(date)
Docker version: $(docker --version)
AWS Region: ${aws_region}
S3 Bucket: ${s3_bucket_name}
ECR Registry: $ECR_REGISTRY
Polars Image: $POLARS_IMAGE
MARKEREOF

echo ""
echo "=== EC2 instance setup complete ==="
echo "Instance is ready for Polars ETL benchmarking with Docker"
echo ""
echo "To run a benchmark:"
echo "  run-polars-benchmark.sh <data_size>"
echo ""
echo "Examples:"
echo "  run-polars-benchmark.sh tiny"
echo "  run-polars-benchmark.sh small"
echo "  run-polars-benchmark.sh medium"
echo ""
echo "Logs will be in: /var/log/polars-etl/"
echo ""
echo "Setup log: /var/log/user-data.log"
echo "Completion marker: /var/log/polars-setup-complete.txt"
echo ""
