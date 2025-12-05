#!/bin/bash
# EC2 Deployment Script for Polars ETL
# This script deploys an EC2 instance using Terraform and verifies the setup
#
# Usage:
#   ./deploy_ec2_polars.sh [INSTANCE_TYPE] [ARCHITECTURE]
#
# Examples:
#   ./deploy_ec2_polars.sh r6i.2xlarge x86_64
#   ./deploy_ec2_polars.sh r7g.2xlarge arm64

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Default values
INSTANCE_TYPE="${1:-r6i.2xlarge}"
ARCHITECTURE="${2:-x86_64}"
CREATE_INSTANCE="${3:-true}"
ALLOCATE_EIP="${4:-false}"

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
echo "EC2 Polars ETL Deployment Script"
echo "=========================================="
echo "Instance Type: $INSTANCE_TYPE"
echo "Architecture: $ARCHITECTURE"
echo "Create Instance: $CREATE_INSTANCE"
echo "Allocate EIP: $ALLOCATE_EIP"
echo "=========================================="
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    log_error "Terraform is not installed. Please install Terraform first."
    exit 1
fi
log_success "Terraform is installed: $(terraform version -json | jq -r '.terraform_version')"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi
log_success "AWS CLI is installed: $(aws --version)"

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    log_warning "jq is not installed. Some features may not work. Install with: sudo dnf install jq"
fi

# Check AWS credentials
log_info "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials are not configured. Please run 'aws configure' first."
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
log_success "AWS Account ID: $AWS_ACCOUNT_ID"
log_success "AWS Region: $AWS_REGION"

# Check if terraform directory exists
if [ ! -d "$TERRAFORM_DIR" ]; then
    log_error "Terraform directory not found: $TERRAFORM_DIR"
    exit 1
fi

# Navigate to Terraform directory
cd "$TERRAFORM_DIR"
log_info "Working directory: $(pwd)"

# Check if terraform.tfvars exists, create if not
if [ ! -f "terraform.tfvars" ]; then
    log_warning "terraform.tfvars not found. Creating default configuration..."
    cat > terraform.tfvars <<EOF
# AWS Configuration
aws_region  = "$AWS_REGION"
environment = "dev"

# EKS Configuration
cluster_name    = "etl-benchmark-cluster"
cluster_version = "1.28"

# EC2 Configuration for Polars
ec2_create_instance = $CREATE_INSTANCE
ec2_instance_type   = "$INSTANCE_TYPE"
ec2_architecture    = "$ARCHITECTURE"
ec2_allocate_eip    = $ALLOCATE_EIP

# Note: Set ec2_key_name to your SSH key pair name for SSH access
# ec2_key_name = "your-key-name"

# Git repository (update with your actual repo)
# git_repo_url = "https://github.com/yourusername/etl-benchmark.git"
# git_branch   = "main"
EOF
    log_success "Created terraform.tfvars with default values"
    log_warning "Please review and update terraform.tfvars before proceeding"
    log_warning "Especially set ec2_key_name if you want SSH access"
else
    log_info "Using existing terraform.tfvars"

    # Update EC2 variables in existing tfvars
    log_info "Updating EC2 configuration in terraform.tfvars..."

    # Backup existing tfvars
    cp terraform.tfvars terraform.tfvars.backup

    # Update or add EC2 variables
    if grep -q "ec2_create_instance" terraform.tfvars; then
        sed -i "s/ec2_create_instance.*/ec2_create_instance = $CREATE_INSTANCE/" terraform.tfvars
    else
        echo "ec2_create_instance = $CREATE_INSTANCE" >> terraform.tfvars
    fi

    if grep -q "ec2_instance_type" terraform.tfvars; then
        sed -i "s/ec2_instance_type.*/ec2_instance_type = \"$INSTANCE_TYPE\"/" terraform.tfvars
    else
        echo "ec2_instance_type = \"$INSTANCE_TYPE\"" >> terraform.tfvars
    fi

    if grep -q "ec2_architecture" terraform.tfvars; then
        sed -i "s/ec2_architecture.*/ec2_architecture = \"$ARCHITECTURE\"/" terraform.tfvars
    else
        echo "ec2_architecture = \"$ARCHITECTURE\"" >> terraform.tfvars
    fi

    log_success "Updated EC2 configuration"
fi

# Initialize Terraform
log_info "Initializing Terraform..."
if terraform init -upgrade; then
    log_success "Terraform initialized successfully"
else
    log_error "Terraform initialization failed"
    exit 1
fi

# Validate Terraform configuration
log_info "Validating Terraform configuration..."
if terraform validate; then
    log_success "Terraform configuration is valid"
else
    log_error "Terraform validation failed"
    exit 1
fi

# Plan Terraform changes
log_info "Planning Terraform changes..."
if terraform plan -out=tfplan; then
    log_success "Terraform plan created successfully"
else
    log_error "Terraform plan failed"
    exit 1
fi

# Ask for confirmation
echo ""
log_warning "Review the Terraform plan above."
read -p "Do you want to apply these changes? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Deployment cancelled by user"
    rm -f tfplan
    exit 0
fi

# Apply Terraform changes
log_info "Applying Terraform changes..."
if terraform apply tfplan; then
    log_success "Terraform apply completed successfully"
    rm -f tfplan
else
    log_error "Terraform apply failed"
    rm -f tfplan
    exit 1
fi

# Get outputs
log_info "Retrieving deployment information..."

INSTANCE_ID=$(terraform output -raw ec2_instance_id 2>/dev/null || echo "")
INSTANCE_PUBLIC_IP=$(terraform output -raw ec2_instance_public_ip 2>/dev/null || echo "")
SSH_COMMAND=$(terraform output -raw ec2_ssh_command 2>/dev/null || echo "")
LOG_GROUP=$(terraform output -raw ec2_cloudwatch_log_group 2>/dev/null || echo "")

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
    log_warning "No EC2 instance was created (ec2_create_instance may be false)"
    exit 0
fi

echo ""
echo "=========================================="
echo "Deployment Information"
echo "=========================================="
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $INSTANCE_PUBLIC_IP"
echo "SSH Command: $SSH_COMMAND"
echo "CloudWatch Log Group: $LOG_GROUP"
echo "=========================================="
echo ""

# Wait for instance to be ready
log_info "Waiting for instance to be ready..."
log_info "This may take 2-3 minutes for the instance to boot and run user data..."

MAX_WAIT=300  # 5 minutes
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    INSTANCE_STATE=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --region "$AWS_REGION" \
        --query 'Reservations[0].Instances[0].State.Name' \
        --output text 2>/dev/null || echo "unknown")

    if [ "$INSTANCE_STATE" == "running" ]; then
        log_success "Instance is running"
        break
    fi

    log_info "Instance state: $INSTANCE_STATE (waiting...)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$INSTANCE_STATE" != "running" ]; then
    log_error "Instance did not reach running state within $MAX_WAIT seconds"
    exit 1
fi

# Wait a bit more for user data to complete
log_info "Waiting for user data script to complete (60 seconds)..."
sleep 60

# Verify Polars installation (if we have SSH access)
if [ -n "$SSH_COMMAND" ] && [ "$SSH_COMMAND" != "No SSH key configured" ]; then
    log_info "Attempting to verify Polars installation via SSH..."

    # Extract key file and host from SSH command
    if [[ $SSH_COMMAND =~ -i\ ([^\ ]+)\ ec2-user@([^\ ]+) ]]; then
        KEY_FILE="${BASH_REMATCH[1]}"
        HOST="${BASH_REMATCH[2]}"

        # Wait for SSH to be available
        log_info "Waiting for SSH to be available..."
        MAX_SSH_WAIT=120
        SSH_ELAPSED=0

        while [ $SSH_ELAPSED -lt $MAX_SSH_WAIT ]; do
            if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
                ec2-user@"$HOST" "echo 'SSH connection successful'" &>/dev/null; then
                log_success "SSH connection established"
                break
            fi
            sleep 5
            SSH_ELAPSED=$((SSH_ELAPSED + 5))
        done

        if [ $SSH_ELAPSED -ge $MAX_SSH_WAIT ]; then
            log_warning "Could not establish SSH connection within $MAX_SSH_WAIT seconds"
            log_warning "You can manually verify the setup later using: $SSH_COMMAND"
        else
            # Verify installation
            log_info "Verifying Polars installation..."

            if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@"$HOST" \
                "sudo cat /opt/etl-benchmark/setup_complete.txt" 2>/dev/null; then
                log_success "Setup verification successful"
            else
                log_warning "Could not verify setup. User data may still be running."
                log_info "Check CloudWatch logs: $LOG_GROUP"
            fi
        fi
    fi
else
    log_warning "No SSH key configured. Cannot verify installation remotely."
    log_info "Check CloudWatch logs for setup progress: $LOG_GROUP"
fi

# Test S3 access from instance (if we have SSH)
if [ -n "$SSH_COMMAND" ] && [ "$SSH_COMMAND" != "No SSH key configured" ]; then
    log_info "Testing S3 access from instance..."

    if [[ $SSH_COMMAND =~ -i\ ([^\ ]+)\ ec2-user@([^\ ]+) ]]; then
        KEY_FILE="${BASH_REMATCH[1]}"
        HOST="${BASH_REMATCH[2]}"

        if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@"$HOST" \
            "aws s3 ls s3://nyc-tlc/trip\ data/ --max-items 5" &>/dev/null; then
            log_success "S3 access verified - can read NYC TLC bucket"
        else
            log_warning "Could not verify S3 access to NYC TLC bucket"
        fi
    fi
fi

# Display next steps
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Connect to instance:"
echo "   $SSH_COMMAND"
echo ""
echo "2. View system information:"
echo "   sudo /opt/etl-benchmark/system_info.sh"
echo ""
echo "3. Run a benchmark:"
echo "   sudo /opt/etl-benchmark/run_benchmark.sh small"
echo ""
echo "4. View logs:"
echo "   sudo tail -f /opt/etl-benchmark/logs/etl.log"
echo ""
echo "5. Monitor in CloudWatch:"
echo "   aws logs tail $LOG_GROUP --follow"
echo ""
echo "6. To destroy the instance:"
echo "   cd $TERRAFORM_DIR && terraform destroy"
echo ""
echo "=========================================="
