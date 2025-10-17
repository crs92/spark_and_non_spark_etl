#!/bin/bash
# Test script for docker-compose setup with podman-compose

set -e

echo "=========================================="
echo "Testing Docker Compose Setup"
echo "=========================================="

# Detect podman/docker
if command -v podman &> /dev/null; then
    DOCKER_CMD="podman"
    COMPOSE_CMD="podman compose"
    echo "Using podman"
elif command -v docker &> /dev/null; then
    DOCKER_CMD="docker"
    COMPOSE_CMD="docker compose"
    echo "Using docker"
else
    echo "Error: Neither podman nor docker found"
    exit 1
fi

echo ""
echo "Test 1: Verify docker-compose.yml syntax"
echo "--------------------------------------"
$COMPOSE_CMD config --services
echo "✓ docker-compose.yml is valid"

echo ""
echo "Test 2: Start infrastructure services"
echo "--------------------------------------"
$COMPOSE_CMD down -v 2>/dev/null || true
$COMPOSE_CMD up -d minio postgres
echo "Waiting for services to be healthy..."
sleep 15

echo ""
echo "Test 3: Check service health"
echo "--------------------------------------"
$DOCKER_CMD ps --format "table {{.Names}}\t{{.Status}}"

# Check if services are healthy
MINIO_STATUS=$($DOCKER_CMD ps --filter "name=minio-iceberg" --format "{{.Status}}")
POSTGRES_STATUS=$($DOCKER_CMD ps --filter "name=postgres-iceberg" --format "{{.Status}}")

if [[ $MINIO_STATUS == *"healthy"* ]]; then
    echo "✓ MinIO is healthy"
else
    echo "✗ MinIO is not healthy: $MINIO_STATUS"
    exit 1
fi

if [[ $POSTGRES_STATUS == *"healthy"* ]]; then
    echo "✓ PostgreSQL is healthy"
else
    echo "✗ PostgreSQL is not healthy: $POSTGRES_STATUS"
    exit 1
fi

echo ""
echo "Test 4: Test Pythonic ETL container"
echo "--------------------------------------"
$DOCKER_CMD run --rm --network spark_and_non_spark_etl_etl-network pythonic-etl python -c "
import polars
import duckdb
print('✓ Pythonic ETL dependencies OK')
"

echo ""
echo "Test 5: Test Spark ETL container"
echo "--------------------------------------"
$DOCKER_CMD run --rm --network spark_and_non_spark_etl_etl-network spark-etl python -c "
import pyspark
print('✓ Spark ETL dependencies OK')
"

echo ""
echo "Test 6: Test network connectivity"
echo "--------------------------------------"
$DOCKER_CMD run --rm --network spark_and_non_spark_etl_etl-network pythonic-etl bash -c "
curl -s http://minio:9000/minio/health/live > /dev/null && echo '✓ Can reach MinIO'
"

echo ""
echo "=========================================="
echo "✓ All docker-compose tests passed!"
echo "=========================================="
echo ""
echo "Infrastructure is running:"
echo "  - MinIO Console: http://localhost:9001"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "To stop services: make docker-down"
