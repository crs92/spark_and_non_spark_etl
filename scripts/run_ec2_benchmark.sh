#!/bin/bash
# EC2 Benchmark Execution Script for Polars ETL
# This script connects to an EC2 instance, runs a benchmark, and collects results
#
# Usage:
#   ./run_ec2_benchmark.sh [DATA_SIZE] [INSTANCE_ID] [KEY_FILE]
#
# Examples:
#   ./run_ec2_benchmark.sh small                    # Auto-detect instance
#   ./run_ec2_benchmark.sh medium i-1234567890abcdef0 ~/.ssh/my-key.pem
#   ./run_ec2_benchmark.sh large                    # Auto-detect instance and key

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
RESULTS_DIR="$PROJECT_ROOT/benchmark_results"

# Arguments
DATA_SIZE="${1:-small}"
INSTANCE_ID="${2:-}"
KEY_FILE="${3:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
echo "=========================================="
echo "EC2 Polars Benchmark Execution Script"
echo "=========================================="
echo "Data Size: $DATA_SIZE"
echo "=========================================="
echo ""

# Validate data size
VALID_SIZES=("tiny" "small" "medium" "large" "xlarge" "xxlarge")
if [[ ! " ${VALID_SIZES[@]} " =~ " ${DATA_SIZE} " ]]; then
    log_error "Invalid data size: $DATA_SIZE"
    log_error "Valid sizes: ${VALID_SIZES[*]}"
    exit 1
fi

# Check prerequisites
log_info "Checking prerequisites..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials are not configured. Please run 'aws configure' first."
    exit 1
fi

AWS_REGION=$(aws configure get region || echo "us-east-1")
log_success "AWS Region: $AWS_REGION"

# Auto-detect instance ID if not provided
if [ -z "$INSTANCE_ID" ]; then
    log_info "Auto-detecting EC2 instance..."

    # Try to get from Terraform output
    if [ -d "$TERRAFORM_DIR" ]; then
        cd "$TERRAFORM_DIR"
        INSTANCE_ID=$(terraform output -raw ec2_instance_id 2>/dev/null || echo "")

        if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "null" ]; then
            log_success "Found instance from Terraform: $INSTANCE_ID"
        fi
    fi

    # If still not found, search by tags
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
        log_info "Searching for instance by tags..."
        INSTANCE_ID=$(aws ec2 describe-instances \
            --region "$AWS_REGION" \
            --filters "Name=tag:Purpose,Values=polars-etl-benchmark" \
                      "Name=instance-state-name,Values=running" \
            --query 'Reservations[0].Instances[0].InstanceId' \
            --output text 2>/dev/null || echo "")

        if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "None" ]; then
            log_success "Found instance by tags: $INSTANCE_ID"
        else
            log_error "Could not find EC2 instance. Please provide instance ID as argument."
            exit 1
        fi
    fi
fi

# Get instance information
log_info "Getting instance information..."
INSTANCE_INFO=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$AWS_REGION" \
    --output json 2>/dev/null)

if [ -z "$INSTANCE_INFO" ]; then
    log_error "Could not get information for instance: $INSTANCE_ID"
    exit 1
fi

INSTANCE_STATE=$(echo "$INSTANCE_INFO" | jq -r '.Reservations[0].Instances[0].State.Name')
INSTANCE_TYPE=$(echo "$INSTANCE_INFO" | jq -r '.Reservations[0].Instances[0].InstanceType')
INSTANCE_PUBLIC_IP=$(echo "$INSTANCE_INFO" | jq -r '.Reservations[0].Instances[0].PublicIpAddress // empty')
INSTANCE_PRIVATE_IP=$(echo "$INSTANCE_INFO" | jq -r '.Reservations[0].Instances[0].PrivateIpAddress')
KEY_NAME=$(echo "$INSTANCE_INFO" | jq -r '.Reservations[0].Instances[0].KeyName // empty')

log_success "Instance Type: $INSTANCE_TYPE"
log_success "Instance State: $INSTANCE_STATE"
log_success "Public IP: ${INSTANCE_PUBLIC_IP:-N/A}"
log_success "Private IP: $INSTANCE_PRIVATE_IP"

# Check if instance is running
if [ "$INSTANCE_STATE" != "running" ]; then
    log_error "Instance is not running (state: $INSTANCE_STATE)"
    exit 1
fi

# Auto-detect key file if not provided
if [ -z "$KEY_FILE" ] && [ -n "$KEY_NAME" ]; then
    log_info "Auto-detecting SSH key file..."

    # Common key locations
    POSSIBLE_KEYS=(
        "$HOME/.ssh/$KEY_NAME.pem"
        "$HOME/.ssh/$KEY_NAME"
        "$HOME/.ssh/id_rsa"
        "$HOME/.ssh/id_ed25519"
    )

    for key in "${POSSIBLE_KEYS[@]}"; do
        if [ -f "$key" ]; then
            KEY_FILE="$key"
            log_success "Found key file: $KEY_FILE"
            break
        fi
    done

    if [ -z "$KEY_FILE" ]; then
        log_error "Could not find SSH key file for key name: $KEY_NAME"
        log_error "Please provide key file path as third argument"
        exit 1
    fi
fi

# Determine SSH host
SSH_HOST="${INSTANCE_PUBLIC_IP:-$INSTANCE_PRIVATE_IP}"
if [ -z "$SSH_HOST" ]; then
    log_error "Could not determine SSH host (no public or private IP)"
    exit 1
fi

# Test SSH connection
log_info "Testing SSH connection to $SSH_HOST..."
if ! ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    ec2-user@"$SSH_HOST" "echo 'SSH connection successful'" &>/dev/null; then
    log_error "Could not establish SSH connection to instance"
    log_error "Make sure the security group allows SSH from your IP"
    exit 1
fi
log_success "SSH connection successful"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Generate timestamp for this run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_PREFIX="polars_ec2_${DATA_SIZE}_${INSTANCE_TYPE}_${TIMESTAMP}"

log_info "Starting benchmark execution..."
echo ""
echo "=========================================="
echo "Benchmark Configuration"
echo "=========================================="
echo "Data Size: $DATA_SIZE"
echo "Instance Type: $INSTANCE_TYPE"
echo "Instance ID: $INSTANCE_ID"
echo "Timestamp: $TIMESTAMP"
echo "Result Prefix: $RESULT_PREFIX"
echo "=========================================="
echo ""

# Record start time
START_TIME=$(date +%s)

# Execute benchmark on EC2 instance
log_info "Executing benchmark on EC2 instance..."
log_info "This may take several minutes depending on data size..."

SSH_CMD="ssh -i $KEY_FILE -o StrictHostKeyChecking=no ec2-user@$SSH_HOST"

# Run the benchmark
if $SSH_CMD "sudo /opt/etl-benchmark/run_benchmark.sh $DATA_SIZE $RESULT_PREFIX" 2>&1 | tee "$RESULTS_DIR/${RESULT_PREFIX}_console.log"; then
    log_success "Benchmark execution completed"
else
    log_error "Benchmark execution failed"
    log_error "Check console log: $RESULTS_DIR/${RESULT_PREFIX}_console.log"
    exit 1
fi

# Record end time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log_success "Benchmark completed in $DURATION seconds"

# Collect metrics from CloudWatch
log_info "Collecting CloudWatch metrics..."

# Get CloudWatch log group
LOG_GROUP="/aws/ec2/etl-benchmark-polars-etl"

# Download ETL logs
log_info "Downloading ETL logs..."
aws logs tail "$LOG_GROUP" \
    --log-stream-names "${INSTANCE_ID}/etl" \
    --since 1h \
    --format short \
    > "$RESULTS_DIR/${RESULT_PREFIX}_etl.log" 2>/dev/null || log_warning "Could not download ETL logs"

# Collect CloudWatch metrics
log_info "Collecting CloudWatch metrics for the benchmark period..."

METRICS_FILE="$RESULTS_DIR/${RESULT_PREFIX}_metrics.json"

cat > "$METRICS_FILE" <<EOF
{
  "benchmark_info": {
    "data_size": "$DATA_SIZE",
    "instance_type": "$INSTANCE_TYPE",
    "instance_id": "$INSTANCE_ID",
    "timestamp": "$TIMESTAMP",
    "duration_seconds": $DURATION,
    "start_time": $START_TIME,
    "end_time": $END_TIME
  },
  "cloudwatch_metrics": {}
}
EOF

# Query CloudWatch metrics
METRIC_NAMESPACE="ETLBenchmark/EC2/Polars"
METRIC_NAMES=("CPU_USER" "CPU_SYSTEM" "CPU_IOWAIT" "MEM_USED_PERCENT" "DISK_READ_BYTES" "DISK_WRITE_BYTES" "NET_BYTES_SENT" "NET_BYTES_RECV")

for METRIC_NAME in "${METRIC_NAMES[@]}"; do
    log_info "Querying metric: $METRIC_NAME"

    METRIC_DATA=$(aws cloudwatch get-metric-statistics \
        --namespace "$METRIC_NAMESPACE" \
        --metric-name "$METRIC_NAME" \
        --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
        --start-time "$(date -u -d "@$START_TIME" +%Y-%m-%dT%H:%M:%S)" \
        --end-time "$(date -u -d "@$END_TIME" +%Y-%m-%dT%H:%M:%S)" \
        --period 60 \
        --statistics Average,Maximum,Minimum \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Datapoints": []}')

    # Add to metrics file (requires jq)
    if command -v jq &> /dev/null; then
        TEMP_FILE=$(mktemp)
        jq --arg metric "$METRIC_NAME" --argjson data "$METRIC_DATA" \
            '.cloudwatch_metrics[$metric] = $data' \
            "$METRICS_FILE" > "$TEMP_FILE"
        mv "$TEMP_FILE" "$METRICS_FILE"
    fi
done

log_success "Metrics collected: $METRICS_FILE"

# Download results from S3
log_info "Downloading results from S3..."

# Get S3 bucket name
S3_BUCKET=$(aws s3 ls | grep etl-benchmark-data | awk '{print $3}' | head -1)

if [ -n "$S3_BUCKET" ]; then
    log_info "S3 Bucket: $S3_BUCKET"

    # Download results
    S3_PREFIX="polars/${DATA_SIZE}/${RESULT_PREFIX}"

    if aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" &>/dev/null; then
        aws s3 sync "s3://$S3_BUCKET/$S3_PREFIX/" "$RESULTS_DIR/${RESULT_PREFIX}_s3_results/" \
            --region "$AWS_REGION"
        log_success "Results downloaded from S3"
    else
        log_warning "No results found in S3 at: s3://$S3_BUCKET/$S3_PREFIX/"
    fi
else
    log_warning "Could not find S3 bucket"
fi

# Create summary report
log_info "Creating summary report..."

SUMMARY_FILE="$RESULTS_DIR/${RESULT_PREFIX}_summary.txt"

cat > "$SUMMARY_FILE" <<EOF
========================================
EC2 Polars Benchmark Summary
========================================

Benchmark Configuration:
  Data Size: $DATA_SIZE
  Instance Type: $INSTANCE_TYPE
  Instance ID: $INSTANCE_ID
  Timestamp: $TIMESTAMP

Execution:
  Start Time: $(date -d "@$START_TIME" '+%Y-%m-%d %H:%M:%S')
  End Time: $(date -d "@$END_TIME" '+%Y-%m-%d %H:%M:%S')
  Duration: $DURATION seconds ($(($DURATION / 60)) minutes)

Results Location:
  Console Log: $RESULTS_DIR/${RESULT_PREFIX}_console.log
  ETL Log: $RESULTS_DIR/${RESULT_PREFIX}_etl.log
  Metrics: $METRICS_FILE
  S3 Results: $RESULTS_DIR/${RESULT_PREFIX}_s3_results/
  Summary: $SUMMARY_FILE

CloudWatch:
  Log Group: $LOG_GROUP
  Log Stream: ${INSTANCE_ID}/etl

========================================
EOF

cat "$SUMMARY_FILE"

# Display next steps
echo ""
echo "=========================================="
echo "Benchmark Complete!"
echo "=========================================="
echo ""
echo "Results saved to: $RESULTS_DIR"
echo ""
echo "Next steps:"
echo ""
echo "1. View summary:"
echo "   cat $SUMMARY_FILE"
echo ""
echo "2. View console output:"
echo "   cat $RESULTS_DIR/${RESULT_PREFIX}_console.log"
echo ""
echo "3. View ETL logs:"
echo "   cat $RESULTS_DIR/${RESULT_PREFIX}_etl.log"
echo ""
echo "4. View metrics:"
echo "   cat $METRICS_FILE | jq"
echo ""
echo "5. Run another benchmark:"
echo "   ./scripts/run_ec2_benchmark.sh <data_size>"
echo ""
echo "6. Compare with Spark results:"
echo "   # Run Spark benchmark and compare"
echo ""
echo "=========================================="

log_success "All done!"
