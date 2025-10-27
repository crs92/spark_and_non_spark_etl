#!/bin/bash
# ETL Framework Comparison Script

set -e

RESULTS_DIR="./benchmark_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "ETL Framework Comparison"
echo "=========================================="
echo ""

# Create results directory
mkdir -p $RESULTS_DIR

# Run Pythonic ETL
echo "Running Pythonic ETL..."
START=$(date +%s)
podman run --rm localhost/pythonic-etl python -m src.etl.polars_etl > ${RESULTS_DIR}/pythonic_${TIMESTAMP}.log 2>&1
END=$(date +%s)
PYTHONIC_TIME=$((END - START))

echo "✓ Pythonic completed in ${PYTHONIC_TIME}s"
echo ""

# Run Spark ETL
echo "Running Spark ETL..."
START=$(date +%s)
podman run --rm localhost/spark-etl python -m src.etl.spark_etl > ${RESULTS_DIR}/spark_${TIMESTAMP}.log 2>&1
END=$(date +%s)
SPARK_TIME=$((END - START))

echo "✓ Spark completed in ${SPARK_TIME}s"
echo ""

# Generate comparison report
echo "=========================================="
echo "COMPARISON RESULTS"
echo "=========================================="
printf "%-20s %15s\n" "Framework" "Time (seconds)"
echo "--------------------------------------------"
printf "%-20s %15d\n" "Pythonic (Polars)" "$PYTHONIC_TIME"
printf "%-20s %15d\n" "Spark" "$SPARK_TIME"
echo "--------------------------------------------"

# Calculate speedup
if [ "$PYTHONIC_TIME" -lt "$SPARK_TIME" ]; then
    SPEEDUP=$((SPARK_TIME / PYTHONIC_TIME))
    WINNER="Pythonic"
    echo "Winner: Pythonic (~${SPEEDUP}x faster)"
else
    SPEEDUP=$((PYTHONIC_TIME / SPARK_TIME))
    WINNER="Spark"
    echo "Winner: Spark (~${SPEEDUP}x faster)"
fi

echo ""
echo "Details:"
echo "  - Pythonic logs: ${RESULTS_DIR}/pythonic_${TIMESTAMP}.log"
echo "  - Spark logs: ${RESULTS_DIR}/spark_${TIMESTAMP}.log"
echo ""

# Save JSON results
cat > ${RESULTS_DIR}/comparison_${TIMESTAMP}.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "pythonic": {
    "time_seconds": $PYTHONIC_TIME,
    "framework": "Polars + DuckDB"
  },
  "spark": {
    "time_seconds": $SPARK_TIME,
    "framework": "PySpark"
  },
  "winner": "$WINNER",
  "speedup": $SPEEDUP
}
EOF

echo "Results saved to: ${RESULTS_DIR}/comparison_${TIMESTAMP}.json"
echo ""
echo "=========================================="
