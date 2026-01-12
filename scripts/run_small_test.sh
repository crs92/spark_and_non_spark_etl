#!/bin/bash
# Run Spark TPC-H test with small resource requirements

set -e

echo "=========================================="
echo "Running Spark TPC-H (Small Nodes)"
echo "=========================================="
echo ""

# 1. Delete old job
echo "[1/3] Deleting old job..."
kubectl delete sparkapplication spark-tpch-sf10 2>/dev/null || true
kubectl delete sparkapplication spark-tpch-sf10-small 2>/dev/null || true
sleep 5

# 2. Submit new job with reduced resources
echo "[2/3] Submitting job with reduced resources..."
echo "  Driver: 1 core, 2GB RAM"
echo "  Executors: 2 × (1 core, 2GB RAM)"
echo "  Total: 3 cores, 6GB RAM"
echo ""
kubectl apply -f k8s/spark-tpch-sf10-small.yaml

# 3. Monitor
echo "[3/3] Monitoring job..."
echo ""
echo "Waiting for driver pod to be created..."
sleep 10

# Watch pod status
kubectl get pods -l app=spark-tpch-driver -w &
WATCH_PID=$!

# Wait for driver to be ready
echo ""
echo "Waiting for driver to be ready (this may take 2-3 minutes)..."
kubectl wait --for=condition=Ready pod -l app=spark-tpch-driver --timeout=300s 2>/dev/null || true

# Kill watch
kill $WATCH_PID 2>/dev/null || true

# Follow logs
echo ""
echo "=========================================="
echo "Driver Logs"
echo "=========================================="
DRIVER_POD=$(kubectl get pods -l app=spark-tpch-driver -o jsonpath='{.items[0].metadata.name}')
kubectl logs -f "$DRIVER_POD" 2>/dev/null || echo "Driver not ready yet"

echo ""
echo "=========================================="
echo "To check results:"
echo "  aws s3 ls s3://ccorsetti/results/spark/sf10/ --recursive"
echo "=========================================="
