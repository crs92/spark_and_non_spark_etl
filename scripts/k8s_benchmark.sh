#!/bin/bash
# Kubernetes ETL Benchmark Script
# Compares Polars and Spark ETL performance on Kubernetes

set -e

RESULTS_DIR="./benchmark_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_SIZE="${DATA_SIZE:-small}"

echo "=========================================="
echo "Kubernetes ETL Benchmark"
echo "=========================================="
echo "Data Size: ${DATA_SIZE}"
echo "Timestamp: ${TIMESTAMP}"
echo "=========================================="
echo ""

# Create results directory
mkdir -p ${RESULTS_DIR}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    echo "   Please ensure your cluster is running and kubectl is configured."
    exit 1
fi

echo "✓ Kubernetes cluster is accessible"
echo ""

# Function to run ETL job and measure time
run_k8s_job() {
    local framework=$1
    local job_file=$2
    local job_name="${framework}-etl-benchmark-${TIMESTAMP}"

    echo "=========================================="
    echo "Running ${framework} ETL on Kubernetes"
    echo "=========================================="

    # Apply job
    START=$(date +%s)
    kubectl apply -f ${job_file}

    # Wait for job to complete
    echo "Waiting for job to complete..."
    kubectl wait --for=condition=complete --timeout=600s job/${job_name} || {
        echo "❌ Job failed or timed out"
        kubectl logs job/${job_name} || true
        kubectl delete job/${job_name} || true
        return 1
    }

    END=$(date +%s)
    DURATION=$((END - START))

    echo "✓ ${framework} completed in ${DURATION}s"

    # Get logs
    kubectl logs job/${job_name} > ${RESULTS_DIR}/${framework}_k8s_${TIMESTAMP}.log

    # Clean up job
    kubectl delete job/${job_name}

    echo ${DURATION}
}

# Run Polars ETL
echo "Running Polars (Pythonic) ETL..."
POLARS_TIME=$(run_k8s_job "pythonic" "k8s/pythonic-etl-job.yaml")
echo ""

# Run Spark ETL
echo "Running Spark ETL..."
SPARK_TIME=$(run_k8s_job "spark" "k8s/spark-etl-job.yaml")
echo ""

# Generate comparison report
echo "=========================================="
echo "KUBERNETES BENCHMARK RESULTS"
echo "=========================================="
printf "%-20s %15s\n" "Framework" "Time (seconds)"
echo "--------------------------------------------"
printf "%-20s %15d\n" "Polars (Pythonic)" "${POLARS_TIME}"
printf "%-20s %15d\n" "Spark" "${SPARK_TIME}"
echo "--------------------------------------------"

# Calculate winner
if [ "${POLARS_TIME}" -lt "${SPARK_TIME}" ]; then
    SPEEDUP=$((SPARK_TIME * 100 / POLARS_TIME))
    ADVANTAGE=$((SPEEDUP - 100))
    echo "Winner: Polars (${ADVANTAGE}% faster)"
else
    SPEEDUP=$((POLARS_TIME * 100 / SPARK_TIME))
    ADVANTAGE=$((SPEEDUP - 100))
    echo "Winner: Spark (${ADVANTAGE}% faster)"
fi

echo ""
echo "Details:"
echo "  - Polars logs: ${RESULTS_DIR}/pythonic_k8s_${TIMESTAMP}.log"
echo "  - Spark logs: ${RESULTS_DIR}/spark_k8s_${TIMESTAMP}.log"
echo ""

# Save JSON results
cat > ${RESULTS_DIR}/k8s_benchmark_${TIMESTAMP}.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "data_size": "${DATA_SIZE}",
  "platform": "kubernetes",
  "polars": {
    "time_seconds": ${POLARS_TIME},
    "framework": "Polars + DuckDB"
  },
  "spark": {
    "time_seconds": ${SPARK_TIME},
    "framework": "PySpark"
  },
  "winner": "$([ "${POLARS_TIME}" -lt "${SPARK_TIME}" ] && echo "Polars" || echo "Spark")"
}
EOF

echo "Results saved to: ${RESULTS_DIR}/k8s_benchmark_${TIMESTAMP}.json"
echo ""
echo "=========================================="
