#!/bin/bash
# Deploy and manage Spark NYC Taxi benchmarks
# Usage: ./deploy-spark-benchmark.sh [command] [size]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="default"
SIZES=("tiny" "small" "medium" "large" "xlarge")

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    print_success "kubectl found"

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    print_success "Connected to Kubernetes cluster"

    # Check Spark Operator
    if ! kubectl get deployment -n spark-operator spark-operator &> /dev/null; then
        print_error "Spark Operator not found. Please install Spark Operator."
        exit 1
    fi
    print_success "Spark Operator is running"

    # Check ServiceAccount
    if ! kubectl get sa spark-sa -n ${NAMESPACE} &> /dev/null; then
        print_error "ServiceAccount 'spark-sa' not found in namespace ${NAMESPACE}"
        exit 1
    fi
    print_success "ServiceAccount 'spark-sa' exists"

    echo ""
}

# Validate size parameter
validate_size() {
    local size=$1
    if [[ ! " ${SIZES[@]} " =~ " ${size} " ]]; then
        print_error "Invalid size: ${size}"
        echo "Valid sizes: ${SIZES[*]}"
        exit 1
    fi
}

# Deploy a SparkApplication
deploy() {
    local size=$1
    validate_size "${size}"

    print_header "Deploying Spark NYC Taxi ETL - ${size} dataset"

    local manifest="k8s/spark-nyc-taxi-${size}.yaml"

    if [ ! -f "${manifest}" ]; then
        print_error "Manifest not found: ${manifest}"
        exit 1
    fi

    # Check if already exists
    if kubectl get sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE} &> /dev/null; then
        print_warning "SparkApplication 'spark-nyc-taxi-${size}' already exists"
        read -p "Delete and redeploy? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl delete sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE}
            sleep 5
        else
            print_info "Skipping deployment"
            exit 0
        fi
    fi

    # Apply manifest
    kubectl apply -f "${manifest}"
    print_success "SparkApplication deployed"

    # Wait for driver pod to start
    print_info "Waiting for driver pod to start..."
    kubectl wait --for=condition=ready \
        --timeout=300s \
        pod -l spark-role=driver,sparkapplication=spark-nyc-taxi-${size} \
        -n ${NAMESPACE} || true

    print_success "Deployment complete"
    echo ""
    print_info "Monitor with: kubectl logs -f spark-nyc-taxi-${size}-driver"
    print_info "Check status: kubectl get sparkapplication spark-nyc-taxi-${size}"
}

# Monitor a SparkApplication
monitor() {
    local size=$1
    validate_size "${size}"

    print_header "Monitoring Spark NYC Taxi ETL - ${size} dataset"

    # Check if exists
    if ! kubectl get sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE} &> /dev/null; then
        print_error "SparkApplication 'spark-nyc-taxi-${size}' not found"
        exit 1
    fi

    # Show status
    echo ""
    print_info "SparkApplication Status:"
    kubectl get sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE}

    echo ""
    print_info "Pods:"
    kubectl get pods -l sparkapplication=spark-nyc-taxi-${size} -n ${NAMESPACE}

    echo ""
    print_info "Recent Events:"
    kubectl get events --sort-by='.lastTimestamp' -n ${NAMESPACE} | grep "spark-nyc-taxi-${size}" | tail -10

    echo ""
    print_info "Follow driver logs with:"
    echo "  kubectl logs -f spark-nyc-taxi-${size}-driver"
}

# Get logs from a SparkApplication
logs() {
    local size=$1
    validate_size "${size}"

    local driver_pod="spark-nyc-taxi-${size}-driver"

    if ! kubectl get pod "${driver_pod}" -n ${NAMESPACE} &> /dev/null; then
        print_error "Driver pod '${driver_pod}' not found"
        exit 1
    fi

    print_header "Driver Logs - ${size} dataset"
    kubectl logs -f "${driver_pod}" -n ${NAMESPACE}
}

# Delete a SparkApplication
delete() {
    local size=$1
    validate_size "${size}"

    print_header "Deleting Spark NYC Taxi ETL - ${size} dataset"

    if ! kubectl get sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE} &> /dev/null; then
        print_warning "SparkApplication 'spark-nyc-taxi-${size}' not found"
        exit 0
    fi

    kubectl delete sparkapplication "spark-nyc-taxi-${size}" -n ${NAMESPACE}
    print_success "SparkApplication deleted"
}

# List all SparkApplications
list() {
    print_header "NYC Taxi SparkApplications"
    kubectl get sparkapplications -l dataset=nyc-taxi -n ${NAMESPACE}
}

# Run all benchmarks sequentially
run_all() {
    print_header "Running All Benchmarks"

    for size in "${SIZES[@]}"; do
        print_info "Starting ${size} dataset..."
        deploy "${size}"

        # Wait for completion
        print_info "Waiting for ${size} to complete..."
        kubectl wait --for=condition=complete \
            --timeout=2h \
            sparkapplication/spark-nyc-taxi-${size} \
            -n ${NAMESPACE} || print_warning "${size} did not complete successfully"

        # Save logs
        mkdir -p logs
        kubectl logs "spark-nyc-taxi-${size}-driver" -n ${NAMESPACE} > "logs/spark-${size}.log" 2>&1 || true

        # Cleanup
        delete "${size}"

        print_success "Completed ${size} dataset"
        sleep 30
    done

    print_success "All benchmarks complete!"
    print_info "Logs saved to logs/ directory"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [command] [size]

Commands:
  check           Check prerequisites
  deploy <size>   Deploy a SparkApplication for specified size
  monitor <size>  Monitor a running SparkApplication
  logs <size>     Follow driver logs
  delete <size>   Delete a SparkApplication
  list            List all NYC Taxi SparkApplications
  run-all         Run all benchmarks sequentially
  help            Show this help message

Sizes:
  tiny            1 month (~100MB, 3M records)
  small           1 year (~1.2GB, 40M records)
  medium          3 years (~4GB, 120M records)
  large           5 years (~10GB, 200M records)
  xlarge          8 years (~50GB, 500M records)

Examples:
  $0 check
  $0 deploy tiny
  $0 monitor small
  $0 logs medium
  $0 delete large
  $0 list
  $0 run-all

EOF
}

# Main
main() {
    local command=${1:-help}
    local size=$2

    case "${command}" in
        check)
            check_prerequisites
            ;;
        deploy)
            if [ -z "${size}" ]; then
                print_error "Size parameter required"
                usage
                exit 1
            fi
            check_prerequisites
            deploy "${size}"
            ;;
        monitor)
            if [ -z "${size}" ]; then
                print_error "Size parameter required"
                usage
                exit 1
            fi
            monitor "${size}"
            ;;
        logs)
            if [ -z "${size}" ]; then
                print_error "Size parameter required"
                usage
                exit 1
            fi
            logs "${size}"
            ;;
        delete)
            if [ -z "${size}" ]; then
                print_error "Size parameter required"
                usage
                exit 1
            fi
            delete "${size}"
            ;;
        list)
            list
            ;;
        run-all)
            check_prerequisites
            run_all
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            print_error "Unknown command: ${command}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
