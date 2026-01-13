#!/bin/bash
# Helper script for AWS Batch operations
# This script provides convenient commands for managing Batch jobs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get Terraform outputs
get_terraform_output() {
    local output_name=$1
    terraform -chdir=terraform output -raw "$output_name" 2>/dev/null || echo ""
}

# Check if terraform outputs are available
check_terraform() {
    if [ ! -f "terraform/terraform.tfstate" ]; then
        echo -e "${RED}Error: Terraform state not found. Please run 'terraform apply' first.${NC}"
        exit 1
    fi
}

# Get Batch resources
get_batch_resources() {
    check_terraform

    export JOB_QUEUE=$(get_terraform_output "batch_job_queue_name")
    export JOB_DEFINITION=$(get_terraform_output "batch_job_definition_arn")
    export LOG_GROUP=$(get_terraform_output "batch_cloudwatch_log_group")
    export S3_BUCKET=$(get_terraform_output "s3_bucket_name")

    if [ -z "$JOB_QUEUE" ] || [ "$JOB_QUEUE" = "null" ]; then
        echo -e "${RED}Error: Batch resources not found in Terraform state.${NC}"
        echo ""
        echo "The AWS Batch infrastructure is defined in terraform/batch.tf but hasn't been deployed yet."
        echo ""
        echo "To deploy Batch resources:"
        echo "  cd terraform"
        echo "  terraform apply"
        echo ""
        echo "This will create:"
        echo "  - Batch compute environment (Fargate)"
        echo "  - Batch job queue"
        echo "  - Batch job definition"
        echo "  - IAM roles and policies"
        echo "  - CloudWatch log group"
        exit 1
    fi
}

# Command: info
cmd_info() {
    echo -e "${GREEN}=== AWS Batch Resources ===${NC}"
    get_batch_resources
    echo "Job Queue:       $JOB_QUEUE"
    echo "Job Definition:  $JOB_DEFINITION"
    echo "Log Group:       $LOG_GROUP"
    echo "S3 Bucket:       $S3_BUCKET"
}

# Command: submit
cmd_submit() {
    local scale_factor=${1:-10}
    local job_name="polars-tpch-sf${scale_factor}-$(date +%s)"

    get_batch_resources

    echo -e "${GREEN}Submitting Batch job...${NC}"
    echo "Job Name:        $job_name"
    echo "Scale Factor:    $scale_factor"
    echo "S3 Input:        s3://${S3_BUCKET}/tpch-sf${scale_factor}/"
    echo "S3 Output:       s3://${S3_BUCKET}/results/"

    local job_id=$(aws batch submit-job \
        --job-name "$job_name" \
        --job-queue "$JOB_QUEUE" \
        --job-definition "$JOB_DEFINITION" \
        --container-overrides "{
            \"command\": [
                \"--scale-factor\", \"${scale_factor}\",
                \"--s3-input\", \"s3://${S3_BUCKET}/tpch-sf${scale_factor}/\",
                \"--s3-output\", \"s3://${S3_BUCKET}/results/\"
            ]
        }" \
        --query 'jobId' \
        --output text)

    echo -e "${GREEN}Job submitted successfully!${NC}"
    echo "Job ID: $job_id"
    echo ""
    echo "Monitor with:"
    echo "  ./scripts/batch_helper.sh logs $job_id"
    echo "  ./scripts/batch_helper.sh status $job_id"
}

# Command: list
cmd_list() {
    local status=${1:-RUNNING}

    get_batch_resources

    echo -e "${GREEN}=== Batch Jobs (${status}) ===${NC}"
    aws batch list-jobs \
        --job-queue "$JOB_QUEUE" \
        --job-status "$status" \
        --query 'jobSummaryList[*].[jobId,jobName,status,createdAt]' \
        --output table
}

# Command: status
cmd_status() {
    local job_id=$1

    if [ -z "$job_id" ]; then
        echo -e "${RED}Error: Job ID required${NC}"
        echo "Usage: $0 status <job-id>"
        exit 1
    fi

    echo -e "${GREEN}=== Job Status ===${NC}"
    aws batch describe-jobs \
        --jobs "$job_id" \
        --query 'jobs[0].[jobId,jobName,status,statusReason,createdAt,startedAt,stoppedAt]' \
        --output table
}

# Command: logs
cmd_logs() {
    local job_id=$1
    local follow=${2:-false}

    get_batch_resources

    if [ -z "$job_id" ]; then
        echo -e "${YELLOW}No job ID provided. Tailing all logs...${NC}"
        if [ "$follow" = "follow" ] || [ "$follow" = "-f" ]; then
            aws logs tail "$LOG_GROUP" --follow
        else
            aws logs tail "$LOG_GROUP"
        fi
    else
        echo -e "${GREEN}=== Job Logs (${job_id}) ===${NC}"

        # Get log stream name for the job
        local log_stream=$(aws batch describe-jobs \
            --jobs "$job_id" \
            --query 'jobs[0].container.logStreamName' \
            --output text)

        if [ "$log_stream" = "None" ] || [ -z "$log_stream" ]; then
            echo -e "${YELLOW}Job hasn't started yet or logs not available.${NC}"
            echo "Tailing all logs from log group..."
            if [ "$follow" = "follow" ] || [ "$follow" = "-f" ]; then
                aws logs tail "$LOG_GROUP" --follow
            else
                aws logs tail "$LOG_GROUP"
            fi
        else
            echo "Log Stream: $log_stream"
            if [ "$follow" = "follow" ] || [ "$follow" = "-f" ]; then
                aws logs tail "$LOG_GROUP" --follow --log-stream-names "$log_stream"
            else
                aws logs tail "$LOG_GROUP" --log-stream-names "$log_stream"
            fi
        fi
    fi
}

# Command: cancel
cmd_cancel() {
    local job_id=$1
    local reason=${2:-"Cancelled by user"}

    if [ -z "$job_id" ]; then
        echo -e "${RED}Error: Job ID required${NC}"
        echo "Usage: $0 cancel <job-id> [reason]"
        exit 1
    fi

    echo -e "${YELLOW}Cancelling job ${job_id}...${NC}"
    aws batch cancel-job \
        --job-id "$job_id" \
        --reason "$reason"

    echo -e "${GREEN}Job cancelled successfully${NC}"
}

# Command: help
cmd_help() {
    cat << EOF
${GREEN}AWS Batch Helper Script${NC}

Usage: $0 <command> [options]

Commands:
  info                    Show Batch resources (queue, definition, logs)
  submit [scale-factor]   Submit a new job (default: SF 10)
  list [status]           List jobs (default: RUNNING)
                          Status: SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING, SUCCEEDED, FAILED
  status <job-id>         Show detailed job status
  logs [job-id] [follow]  Show job logs (use 'follow' or '-f' to tail)
  cancel <job-id>         Cancel a running job
  help                    Show this help message

Examples:
  # Show Batch resources
  $0 info

  # Submit a job with scale factor 10
  $0 submit 10

  # Submit a job with scale factor 100
  $0 submit 100

  # List running jobs
  $0 list

  # List all jobs (any status)
  $0 list ALL

  # Show job status
  $0 status abc123-def456-789

  # Tail logs for a specific job
  $0 logs abc123-def456-789 follow

  # Tail all logs
  $0 logs "" follow

  # Cancel a job
  $0 cancel abc123-def456-789

Environment Variables:
  AWS_REGION              AWS region (default: from terraform)
  AWS_PROFILE             AWS profile to use

EOF
}

# Main
main() {
    local command=${1:-help}
    shift || true

    case "$command" in
        info)
            cmd_info
            ;;
        submit)
            cmd_submit "$@"
            ;;
        list)
            cmd_list "$@"
            ;;
        status)
            cmd_status "$@"
            ;;
        logs)
            cmd_logs "$@"
            ;;
        cancel)
            cmd_cancel "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            echo -e "${RED}Error: Unknown command '$command'${NC}"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
