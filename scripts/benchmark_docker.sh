#!/bin/bash
# Simple Docker/Podman ETL Benchmark
# Compares Polars vs Spark using containers

set -e

# Configuration
DATA_SIZE="${DATA_SIZE:-small}"
RESULTS_DIR="./benchmark_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Detect container runtime
if command -v podman &> /dev/null; then
    RUNTIME="podman"
elif command -v docker &> /dev/null; then
    RUNTIME="docker"
else
    echo "❌ No container runtime found (docker or podman)"
    exit 1
fi

echo "=========================================="
echo "Docker/Podman ETL Benchmark"
echo "=========================================="
echo "Container Runtime: ${RUNTIME}"
echo "Data Size: ${DATA_SIZE}"
echo "Timestamp: ${TIMESTAMP}"
echo "=========================================="
echo ""

# Create results directory
mkdir -p ${RESULTS_DIR}

# Check if data exists
if [ ! -f "data/generated/bulk/bulk_data_${DATA_SIZE}.parquet" ]; then
    echo "❌ Test data not found!"
    echo "   Please generate data first:"
    echo "   make generate-data-full SIZE=${DATA_SIZE}"
    exit 1
fi

echo "✓ Test data found"
echo ""

# Build images
echo "Building container images..."
echo "----------------------------"

echo "Building pythonic-etl..."
${RUNTIME} build -f Dockerfile.pythonic -t pythonic-etl . > /dev/null 2>&1
echo "✓ pythonic-etl built"

echo "Building spark-etl..."
${RUNTIME} build -f Dockerfile.spark -t spark-etl . > /dev/null 2>&1
echo "✓ spark-etl built"
echo ""

# Function to run ETL in container
run_etl() {
    local framework=$1
    local image=$2
    local mode=$3

    # Print to stderr so it doesn't interfere with return value
    echo "Running ${framework} - ${mode} mode..." >&2

    local input_path
    if [ "${mode}" = "bulk" ]; then
        input_path="/app/data/generated/bulk/bulk_data_${DATA_SIZE}.parquet"
    else
        input_path="/app/data/generated/incremental"
    fi

    local cmd
    if [ "${framework}" = "polars" ]; then
        cmd="python -m src.etl.polars_etl --mode ${mode} --input ${input_path} --output /app/data/output/polars --no-iceberg"
    else
        cmd="python -m src.etl.spark_etl --mode ${mode} --input ${input_path} --output /app/data/output/spark --no-iceberg"
    fi

    START=$(date +%s)

    ${RUNTIME} run --rm \
        -v "$(pwd)/data:/app/data:Z" \
        ${image} \
        ${cmd} > ${RESULTS_DIR}/${framework}_${mode}_${TIMESTAMP}.log 2>&1

    END=$(date +%s)
    DURATION=$((END - START))

    # Print to stderr so it doesn't interfere with return value
    echo "✓ ${framework} ${mode} completed in ${DURATION}s" >&2

    # Only return the duration (to stdout)
    echo ${DURATION}
}

# Run Polars benchmarks
echo "=========================================="
echo "POLARS (Pythonic) ETL"
echo "=========================================="
POLARS_BULK=$(run_etl "polars" "pythonic-etl" "bulk")
POLARS_INCR=$(run_etl "polars" "pythonic-etl" "incremental")
POLARS_TOTAL=$((POLARS_BULK + POLARS_INCR))
echo ""

# Run Spark benchmarks
echo "=========================================="
echo "SPARK ETL"
echo "=========================================="
SPARK_BULK=$(run_etl "spark" "spark-etl" "bulk")
SPARK_INCR=$(run_etl "spark" "spark-etl" "incremental")
SPARK_TOTAL=$((SPARK_BULK + SPARK_INCR))
echo ""

# Generate comparison report
echo "=========================================="
echo "BENCHMARK RESULTS"
echo "=========================================="
echo ""

printf "%-25s %15s %15s %15s\n" "Framework" "Bulk (s)" "Incremental (s)" "Total (s)"
echo "------------------------------------------------------------------------"
printf "%-25s %15d %15d %15d\n" "Polars (Pythonic)" "${POLARS_BULK}" "${POLARS_INCR}" "${POLARS_TOTAL}"
printf "%-25s %15d %15d %15d\n" "Spark" "${SPARK_BULK}" "${SPARK_INCR}" "${SPARK_TOTAL}"
echo "------------------------------------------------------------------------"

# Calculate winners
echo ""
echo "WINNERS:"
echo "--------"

# Bulk winner
if [ "${POLARS_BULK}" -lt "${SPARK_BULK}" ]; then
    BULK_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${SPARK_BULK}/${POLARS_BULK}}")
    echo "Bulk:        Polars (${BULK_SPEEDUP}x faster)"
else
    BULK_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${POLARS_BULK}/${SPARK_BULK}}")
    echo "Bulk:        Spark (${BULK_SPEEDUP}x faster)"
fi

# Incremental winner
if [ "${POLARS_INCR}" -lt "${SPARK_INCR}" ]; then
    INCR_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${SPARK_INCR}/${POLARS_INCR}}")
    echo "Incremental: Polars (${INCR_SPEEDUP}x faster)"
else
    INCR_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${POLARS_INCR}/${SPARK_INCR}}")
    echo "Incremental: Spark (${INCR_SPEEDUP}x faster)"
fi

# Total winner
if [ "${POLARS_TOTAL}" -lt "${SPARK_TOTAL}" ]; then
    TOTAL_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${SPARK_TOTAL}/${POLARS_TOTAL}}")
    echo "Total:       Polars (${TOTAL_SPEEDUP}x faster)"
else
    TOTAL_SPEEDUP=$(awk "BEGIN {printf \"%.2f\", ${POLARS_TOTAL}/${SPARK_TOTAL}}")
    echo "Total:       Spark (${TOTAL_SPEEDUP}x faster)"
fi

echo ""
echo "Logs saved to:"
echo "  - ${RESULTS_DIR}/polars_bulk_${TIMESTAMP}.log"
echo "  - ${RESULTS_DIR}/polars_incremental_${TIMESTAMP}.log"
echo "  - ${RESULTS_DIR}/spark_bulk_${TIMESTAMP}.log"
echo "  - ${RESULTS_DIR}/spark_incremental_${TIMESTAMP}.log"
echo ""

# Save JSON results
cat > ${RESULTS_DIR}/docker_benchmark_${TIMESTAMP}.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "data_size": "${DATA_SIZE}",
  "container_runtime": "${RUNTIME}",
  "polars": {
    "bulk_seconds": ${POLARS_BULK},
    "incremental_seconds": ${POLARS_INCR},
    "total_seconds": ${POLARS_TOTAL}
  },
  "spark": {
    "bulk_seconds": ${SPARK_BULK},
    "incremental_seconds": ${SPARK_INCR},
    "total_seconds": ${SPARK_TOTAL}
  }
}
EOF

echo "Results saved to: ${RESULTS_DIR}/docker_benchmark_${TIMESTAMP}.json"
echo ""
echo "=========================================="
