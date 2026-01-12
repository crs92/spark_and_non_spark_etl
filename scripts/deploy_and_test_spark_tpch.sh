#!/bin/bash
# Deploy EKS infrastructure and test Spark TPC-H ETL
# This script automates the entire deployment and testing process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="${AWS_REGION:-eu-central-1}"
CLUSTER_NAME="etl-benchmark-cluster"
SCALE_FACTOR="${SCALE_FACTOR:-10}"
SKIP_TERRAFORM="${SKIP_TERRAFORM:-false}"
SKIP_DATA_GEN="${SKIP_DATA_GEN:-false}"
SKIP_DOCKER="${SKIP_DOCKER:-false}"

# Function to print colored messages
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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing_tools=()

    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v kubectl >/dev/null 2>&1 || missing_tools+=("kubectl")
    command -v helm >/dev/null 2>&1 || missing_tools+=("helm")

    # Check for docker or podman
    if command -v docker >/dev/null 2>&1; then
        CONTAINER_CMD="docker"
    elif command -v podman >/dev/null 2>&1; then
        CONTAINER_CMD="podman"
        log_info "Using podman as container runtime"
    else
        missing_tools+=("docker or podman")
    fi

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please install missing tools and try again"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials not configured"
        log_info "Run: aws configure"
        exit 1
    fi

    log_success "All prerequisites met (using ${CONTAINER_CMD})"
}

# Function to deploy Terraform infrastructure
deploy_infrastructure() {
    if [ "$SKIP_TERRAFORM" = "true" ]; then
        log_warning "Skipping Terraform deployment (SKIP_TERRAFORM=true)"
        return
    fi

    log_info "Deploying EKS infrastructure with Terraform..."

    cd terraform

    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init

    # Plan
    log_info "Creating Terraform plan..."
    terraform plan -out=tfplan

    # Apply
    log_info "Applying Terraform configuration..."
    log_warning "This will take 15-20 minutes..."
    terraform apply tfplan

    cd ..

    log_success "Infrastructure deployed"
}

# Function to configure kubectl
configure_kubectl() {
    log_info "Configuring kubectl..."

    aws eks update-kubeconfig \
        --region "$AWS_REGION" \
        --name "$CLUSTER_NAME"

    # Wait for nodes to be ready
    log_info "Waiting for nodes to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=300s

    log_success "kubectl configured, nodes ready"
    kubectl get nodes
}

# Function to install Spark Operator
install_spark_operator() {
    log_info "Checking if Spark Operator is installed..."

    if kubectl get namespace spark-operator >/dev/null 2>&1; then
        log_warning "Spark Operator already installed, skipping"
        return
    fi

    log_info "Installing Spark Operator..."

    helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
    helm repo update

    helm install spark-operator spark-operator/spark-operator \
        --namespace spark-operator \
        --create-namespace \
        --set webhook.enable=true \
        --wait

    log_success "Spark Operator installed"
}

# Function to setup Kubernetes RBAC
setup_k8s_rbac() {
    log_info "Setting up Kubernetes RBAC..."

    # Apply RBAC configuration
    kubectl apply -f k8s/spark-rbac.yaml
    kubectl apply -f k8s/service-accounts.yaml

    log_success "RBAC configured"
}

# Function to generate TPC-H data
generate_tpch_data() {
    if [ "$SKIP_DATA_GEN" = "true" ]; then
        log_warning "Skipping data generation (SKIP_DATA_GEN=true)"
        return
    fi

    log_info "Checking if TPC-H SF${SCALE_FACTOR} data exists in S3..."

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local s3_bucket="s3://etl-benchmark-data-${account_id}"
    local s3_path="${s3_bucket}/tpch-sf${SCALE_FACTOR}"

    if aws s3 ls "${s3_path}/customer/" >/dev/null 2>&1; then
        log_warning "TPC-H data already exists in S3, skipping generation"
        return
    fi

    log_info "Generating TPC-H SF${SCALE_FACTOR} data..."
    log_warning "This may take several minutes..."

    python -m src.generation.generate_tpch_data_fast \
        --scale-factor "$SCALE_FACTOR" \
        --bucket "$s3_bucket" \
        --prefix "tpch-sf${SCALE_FACTOR}"

    log_success "TPC-H data generated and uploaded to S3"
}

# Function to build and push Docker image
build_and_push_docker() {
    if [ "$SKIP_DOCKER" = "true" ]; then
        log_warning "Skipping Docker build (SKIP_DOCKER=true)"
        return
    fi

    log_info "Building and pushing Spark Docker image..."

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local ecr_registry="${account_id}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    local image_name="spark-etl"
    local image_tag="latest"

    # ECR login
    log_info "Logging into ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | \
        ${CONTAINER_CMD} login --username AWS --password-stdin "$ecr_registry"

    # Build image
    log_info "Building Docker image with ${CONTAINER_CMD}..."
    ${CONTAINER_CMD} build -f Dockerfile.spark -t "${image_name}:${image_tag}" .

    # Tag image
    ${CONTAINER_CMD} tag "${image_name}:${image_tag}" "${ecr_registry}/${image_name}:${image_tag}"

    # Push image
    log_info "Pushing image to ECR..."
    ${CONTAINER_CMD} push "${ecr_registry}/${image_name}:${image_tag}"

    log_success "Docker image pushed to ECR"
}

# Function to run Spark TPC-H job
run_spark_job() {
    log_info "Submitting Spark TPC-H job (SF${SCALE_FACTOR})..."

    local manifest="k8s/spark-tpch-sf${SCALE_FACTOR}.yaml"

    if [ ! -f "$manifest" ]; then
        log_error "Manifest not found: $manifest"
        exit 1
    fi

    # Delete existing job if present
    kubectl delete sparkapplication "spark-tpch-sf${SCALE_FACTOR}" 2>/dev/null || true

    # Submit job
    kubectl apply -f "$manifest"

    log_success "Spark job submitted"

    # Monitor job
    log_info "Monitoring job status..."
    log_info "Press Ctrl+C to stop monitoring (job will continue running)"

    kubectl get sparkapplications "spark-tpch-sf${SCALE_FACTOR}" -w &
    local watch_pid=$!

    # Wait for driver pod to be created
    sleep 10

    # Follow driver logs
    local driver_pod="spark-tpch-sf${SCALE_FACTOR}-driver"

    log_info "Waiting for driver pod to start..."
    kubectl wait --for=condition=Ready pod/"$driver_pod" --timeout=300s || true

    log_info "Following driver logs..."
    kubectl logs -f "$driver_pod" || true

    # Kill the watch process
    kill $watch_pid 2>/dev/null || true
}

# Function to check job results
check_results() {
    log_info "Checking job results..."

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local s3_bucket="s3://etl-benchmark-data-${account_id}"
    local results_path="${s3_bucket}/results/spark/sf${SCALE_FACTOR}/"

    log_info "Results location: $results_path"

    if aws s3 ls "$results_path" >/dev/null 2>&1; then
        log_success "Results found in S3:"
        aws s3 ls "$results_path" --recursive --human-readable

        # Download latest metrics
        local latest_metrics=$(aws s3 ls "$results_path" --recursive | grep metrics | tail -1 | awk '{print $4}')
        if [ -n "$latest_metrics" ]; then
            log_info "Downloading metrics..."
            aws s3 cp "${s3_bucket}/${latest_metrics}" /tmp/spark_metrics.json
            log_info "Metrics:"
            cat /tmp/spark_metrics.json
        fi
    else
        log_warning "No results found yet"
    fi
}

# Function to cleanup
cleanup() {
    log_info "Cleaning up..."

    # Delete Spark job
    kubectl delete sparkapplication "spark-tpch-sf${SCALE_FACTOR}" 2>/dev/null || true

    log_success "Cleanup complete"
}

# Main execution
main() {
    echo "=========================================="
    echo "Spark TPC-H ETL Deployment & Testing"
    echo "=========================================="
    echo ""
    echo "Configuration:"
    echo "  AWS Region: $AWS_REGION"
    echo "  Cluster: $CLUSTER_NAME"
    echo "  Scale Factor: $SCALE_FACTOR"
    echo "  Skip Terraform: $SKIP_TERRAFORM"
    echo "  Skip Data Gen: $SKIP_DATA_GEN"
    echo "  Skip Docker: $SKIP_DOCKER"
    echo ""

    # Check prerequisites
    check_prerequisites

    # Deploy infrastructure
    deploy_infrastructure

    # Configure kubectl
    configure_kubectl

    # Install Spark Operator
    install_spark_operator

    # Setup RBAC
    setup_k8s_rbac

    # Generate TPC-H data
    generate_tpch_data

    # Build and push Docker image
    build_and_push_docker

    # Run Spark job
    run_spark_job

    # Check results
    check_results

    echo ""
    echo "=========================================="
    log_success "Deployment and testing complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Review results in S3"
    echo "  2. Check CloudWatch logs for detailed metrics"
    echo "  3. Run analysis scripts to compare performance"
    echo ""
    echo "To cleanup:"
    echo "  kubectl delete sparkapplication spark-tpch-sf${SCALE_FACTOR}"
    echo "  cd terraform && terraform destroy"
}

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --scale-factor)
            SCALE_FACTOR="$2"
            shift 2
            ;;
        --skip-terraform)
            SKIP_TERRAFORM="true"
            shift
            ;;
        --skip-data-gen)
            SKIP_DATA_GEN="true"
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER="true"
            shift
            ;;
        --cleanup)
            cleanup
            exit 0
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --scale-factor N      TPC-H scale factor (default: 10)"
            echo "  --skip-terraform      Skip Terraform deployment"
            echo "  --skip-data-gen       Skip TPC-H data generation"
            echo "  --skip-docker         Skip Docker build/push"
            echo "  --cleanup             Cleanup resources and exit"
            echo "  --help                Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  AWS_REGION            AWS region (default: eu-central-1)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main
