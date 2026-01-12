# TPC-H Spark ETL Quick Start

This guide provides quick commands to run the TPC-H benchmark using Spark on EKS.

## Prerequisites

- EKS cluster with Spark Operator installed
- TPC-H data generated and uploaded to S3
- Docker image with `spark_etl_tpch.py` built and pushed to ECR

## Running TPC-H Benchmarks

### Scale Factor 10 (~10GB)

```bash
# Submit the job
kubectl apply -f k8s/spark-tpch-sf10.yaml

# Monitor the job
kubectl get sparkapplications spark-tpch-sf10 -w

# View driver logs
kubectl logs -f spark-tpch-sf10-driver

# Check results
aws s3 ls s3://etl-benchmark-data-764738119924/results/spark/sf10/

# Delete the job
kubectl delete sparkapplication spark-tpch-sf10
```

### Scale Factor 100 (~100GB)

```bash
# Submit the job
kubectl apply -f k8s/spark-tpch-sf100.yaml

# Monitor the job
kubectl get sparkapplications spark-tpch-sf100 -w

# View driver logs
kubectl logs -f spark-tpch-sf100-driver

# Check results
aws s3 ls s3://etl-benchmark-data-764738119924/results/spark/sf100/

# Delete the job
kubectl delete sparkapplication spark-tpch-sf100
```

## TPC-H Query 3 (Shipping Priority)

The implementation executes the following query:

```sql
SELECT
    l_orderkey,
    SUM(l_extendedprice * (1 - l_discount)) AS revenue,
    o_orderdate,
    o_shippriority
FROM
    customer, orders, lineitem
WHERE
    c_mktsegment = 'BUILDING'
    AND c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate < DATE '1995-03-15'
    AND l_shipdate > DATE '1995-03-15'
GROUP BY
    l_orderkey, o_orderdate, o_shippriority
ORDER BY
    revenue DESC, o_orderdate
LIMIT 10
```

## Performance Metrics

The job tracks and outputs:
- **Startup time**: Job submission to execution start
- **Execution time**: Data read to result write
- **Peak memory**: Maximum memory usage
- **Bytes read/written**: S3 I/O metrics
- **Spark App ID**: For CloudWatch correlation

Metrics are written to:
- S3: `s3://bucket/results/spark/sf{N}/metrics_{timestamp}.json`
- Local: `/tmp/output/metrics_{timestamp}.json`

## Troubleshooting

### Check Pod Status
```bash
kubectl get pods -l app=spark-tpch-driver
kubectl get pods -l app=spark-tpch-executor
```

### View All Logs
```bash
# Driver logs
kubectl logs spark-tpch-sf10-driver

# Executor logs (replace pod name)
kubectl logs spark-tpch-sf10-<executor-id>
```

### Check S3 Access
```bash
# Verify Pod Identity is working
kubectl exec -it spark-tpch-sf10-driver -- aws s3 ls s3://etl-benchmark-data-764738119924/
```

### Common Issues

1. **S3 Access Denied**: Verify Pod Identity Association is configured
2. **Out of Memory**: Increase executor memory in manifest
3. **Missing Tables**: Verify TPC-H data was generated correctly

## Resource Configuration

### SF10 Configuration
- Driver: 2 cores, 4GB RAM
- Executors: 4 × (2 cores, 4GB RAM)
- Total: 10 cores, 20GB RAM

### SF100 Configuration
- Driver: 4 cores, 8GB RAM
- Executors: 8 × (4 cores, 8GB RAM)
- Total: 36 cores, 72GB RAM

## Next Steps

1. Generate TPC-H data using `src/generation/generate_tpch_data_fast.py`
2. Build and push Docker image with `spark_etl_tpch.py`
3. Run benchmarks using the commands above
4. Analyze results using `src/analysis/` tools
