#!/bin/bash
# Kubernetes ETL Benchmarking Script

set -e

NAMESPACE=${NAMESPACE:-default}
DATA_SIZE=${DATA_SIZE:-small}
RESULTS_DIR="./benchmark_results"

echo "Starting Kubernetes ETL Benchmark"
echo "Namespace: $NAMESPACE"
echo "Data Size: $DATA_SIZE"

# Create results directory
mkdir -p $RESULTS_DIR

# Function to measure time
measure_time() {
    local start_time=$(date +%s.%N)
    eval "$1"
    local end_time=$(date +%s.%N)
    echo "scale=3; $end_time - $start_time" | bc
}

# Function to benchmark ETL job
benchmark_etl() {
    local stack_type=$1
    local job_file=$2
    local image_name=$3

    echo "=== Benchmarking $stack_type ETL ==="

    # Clean up any existing jobs
    kubectl delete job ${stack_type}-etl-job -n $NAMESPACE --ignore-not-found=true

    # Measure image pull time (by forcing image pull)
    echo "Measuring image pull time for $image_name"
    image_pull_time=$(measure_time "kubectl run temp-${stack_type} --image=$image_name --restart=Never --rm -i --image-pull-policy=Always --dry-run=client > /dev/null")

    # Measure job creation and execution time
    echo "Starting $stack_type ETL job"
    job_start_time=$(date +%s.%N)

    kubectl apply -f $job_file -n $NAMESPACE

    # Wait for job to complete and measure time
    echo "Waiting for $stack_type ETL job to complete..."
    kubectl wait --for=condition=complete job/${stack_type}-etl-job -n $NAMESPACE --timeout=600s

    job_end_time=$(date +%s.%N)
    total_execution_time=$(echo "scale=3; $job_end_time - $job_start_time" | bc)

    # Get pod name
    pod_name=$(kubectl get pods -n $NAMESPACE -l job-name=${stack_type}-etl-job -o jsonpath='{.items[0].metadata.name}')

    # Get resource usage
    echo "Collecting resource metrics for $stack_type"
    kubectl top pod $pod_name -n $NAMESPACE --containers > ${RESULTS_DIR}/${stack_type}_resources.txt || true

    # Get logs
    kubectl logs $pod_name -n $NAMESPACE > ${RESULTS_DIR}/${stack_type}_logs.txt

    # Get job details
    kubectl describe job ${stack_type}-etl-job -n $NAMESPACE > ${RESULTS_DIR}/${stack_type}_job_details.txt

    # Create results summary
    cat > ${RESULTS_DIR}/${stack_type}_summary.json << EOF
{
  "stack_type": "$stack_type",
  "image_pull_time": $image_pull_time,
  "total_execution_time": $total_execution_time,
  "job_start_time": "$job_start_time",
  "job_end_time": "$job_end_time",
  "pod_name": "$pod_name",
  "timestamp": "$(date -Iseconds)"
}
EOF

    echo "$stack_type ETL completed in ${total_execution_time}s"

    # Clean up
    kubectl delete job ${stack_type}-etl-job -n $NAMESPACE
}

# Setup infrastructure (if needed)
echo "Setting up infrastructure..."
kubectl apply -f k8s/infrastructure/ -n $NAMESPACE || true

# Wait for infrastructure to be ready
echo "Waiting for infrastructure to be ready..."
sleep 30

# Benchmark both ETL approaches
benchmark_etl "spark" "k8s/spark-etl-job.yaml" "spark-etl:latest"
benchmark_etl "pythonic" "k8s/pythonic-etl-job.yaml" "pythonic-etl:latest"

# Generate comparison report
echo "Generating comparison report..."
python3 << EOF
import json
import os

results_dir = "$RESULTS_DIR"

# Load results
with open(os.path.join(results_dir, "spark_summary.json")) as f:
    spark_results = json.load(f)

with open(os.path.join(results_dir, "pythonic_summary.json")) as f:
    pythonic_results = json.load(f)

# Generate comparison
print("\n" + "="*60)
print("KUBERNETES ETL COMPARISON RESULTS")
print("="*60)
print(f"{'Metric':<25} {'Pythonic':<15} {'Spark':<15} {'Winner':<10}")
print("-" * 65)

metrics = [
    ("Image Pull Time (s)", "image_pull_time"),
    ("Total Execution (s)", "total_execution_time")
]

for metric_name, key in metrics:
    p_val = pythonic_results[key]
    s_val = spark_results[key]
    winner = "Pythonic" if p_val < s_val else "Spark"
    print(f"{metric_name:<25} {p_val:<15.3f} {s_val:<15.3f} {winner:<10}")

print("\n" + "="*60)

# Save combined results
combined_results = {
    "pythonic": pythonic_results,
    "spark": spark_results,
    "comparison_timestamp": "$(date -Iseconds)"
}

with open(os.path.join(results_dir, "k8s_comparison_results.json"), "w") as f:
    json.dump(combined_results, f, indent=2)

print(f"Results saved to {results_dir}/k8s_comparison_results.json")
EOF

echo "Kubernetes ETL benchmark completed!"
echo "Results available in: $RESULTS_DIR"
