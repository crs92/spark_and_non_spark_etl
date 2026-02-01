"""Multi-job orchestrator for TPC-H benchmark.

This module provides the JobOrchestrator class for submitting and monitoring
concurrent jobs across EKS (PySpark) and AWS Batch (Polars/DuckDB).

The orchestrator:
1. Submits multiple jobs concurrently to both platforms
2. Monitors job execution and records timestamps
3. Calculates startup latency (created → started)
4. Collects metrics from all completed jobs
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from dotenv import load_dotenv
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from src.utils.logging_config import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)


@dataclass
class JobSubmission:
    """Represents a submitted job with creation timestamp."""

    job_id: str
    job_type: str  # 'spark' or 'polars'
    created_at: datetime
    job_name: str
    platform: str  # 'eks' or 'batch'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "created_at": self.created_at.isoformat(),
            "job_name": self.job_name,
            "platform": self.platform,
        }


@dataclass
class JobMetrics:
    """Complete metrics for a completed job."""

    job_id: str
    job_type: str
    job_name: str
    platform: str

    # Timestamps
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    # Calculated metrics
    startup_latency_seconds: float | None
    execution_time_seconds: float | None

    # Job status
    status: str  # 'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED'

    # Additional metrics from job execution (loaded from S3)
    peak_memory_mb: int | None = None
    bytes_read: int | None = None
    bytes_written: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "job_name": self.job_name,
            "platform": self.platform,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "startup_latency_seconds": self.startup_latency_seconds,
            "execution_time_seconds": self.execution_time_seconds,
            "status": self.status,
            "peak_memory_mb": self.peak_memory_mb,
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
        }


class JobOrchestrator:
    """Orchestrates concurrent job execution on EKS and AWS Batch.

    This class handles:
    - Job submission to EKS (Spark) and AWS Batch (Polars)
    - Job monitoring with timestamp recording
    - Startup latency calculation
    - Metrics collection from S3

    Attributes:
        eks_cluster: EKS cluster name
        batch_job_queue: AWS Batch job queue name
        batch_job_definition: AWS Batch job definition name
        k8s_namespace: Kubernetes namespace for Spark jobs
        aws_region: AWS region
        s3_bucket: S3 bucket for metrics
        s3_metrics_prefix: S3 prefix for metrics files
    """

    def __init__(
        self,
        eks_cluster: str | None = None,
        batch_job_queue: str | None = None,
        batch_job_definition: str | None = None,
        k8s_namespace: str | None = None,
        aws_region: str | None = None,
        s3_bucket: str | None = None,
        s3_metrics_prefix: str | None = None,
    ):
        """Initialize JobOrchestrator with AWS and Kubernetes clients.

        Args:
            eks_cluster: EKS cluster name (defaults to EKS_CLUSTER_NAME env var)
            batch_job_queue: AWS Batch job queue (defaults to BATCH_JOB_QUEUE env var)
            batch_job_definition: AWS Batch job definition (defaults to BATCH_JOB_DEFINITION env var)
            k8s_namespace: Kubernetes namespace (defaults to K8S_NAMESPACE env var or 'default')
            aws_region: AWS region (defaults to AWS_REGION env var)
            s3_bucket: S3 bucket name (defaults to S3_BUCKET_NAME env var)
            s3_metrics_prefix: S3 metrics prefix (defaults to S3_METRICS_PREFIX env var or 'metrics')
        """
        # Load configuration from environment variables
        self.eks_cluster = eks_cluster or os.getenv("EKS_CLUSTER_NAME")
        self.batch_job_queue = batch_job_queue or os.getenv("BATCH_JOB_QUEUE")
        self.batch_job_definition = batch_job_definition or os.getenv(
            "BATCH_JOB_DEFINITION"
        )
        self.k8s_namespace = k8s_namespace or os.getenv("K8S_NAMESPACE", "default")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self.s3_bucket = s3_bucket or os.getenv("S3_BUCKET_NAME")
        self.s3_metrics_prefix = s3_metrics_prefix or os.getenv(
            "S3_METRICS_PREFIX", "metrics"
        )

        # Validate required configuration
        if not self.eks_cluster:
            logger.warning(
                "EKS_CLUSTER_NAME not set - Spark job submission will not work"
            )
        if not self.batch_job_queue:
            logger.warning(
                "BATCH_JOB_QUEUE not set - Batch job submission will not work"
            )
        if not self.batch_job_definition:
            logger.warning(
                "BATCH_JOB_DEFINITION not set - Batch job submission will not work"
            )
        if not self.s3_bucket:
            logger.warning("S3_BUCKET_NAME not set - Metrics collection will not work")

        # Initialize boto3 clients
        logger.info(f"Initializing AWS clients for region: {self.aws_region}")
        self.batch_client = boto3.client("batch", region_name=self.aws_region)
        self.s3_client = boto3.client("s3", region_name=self.aws_region)
        self.eks_client = boto3.client("eks", region_name=self.aws_region)

        # Initialize Kubernetes client
        logger.info(f"Initializing Kubernetes client for cluster: {self.eks_cluster}")
        try:
            # Try to load in-cluster config first (for running inside K8s)
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            # Fall back to kubeconfig file (for local development)
            try:
                config.load_kube_config()
                logger.info("Loaded Kubernetes configuration from kubeconfig")
            except config.ConfigException as e:
                logger.warning(
                    f"Failed to load Kubernetes configuration: {e}. "
                    "Spark job submission will not work."
                )

        # Create Kubernetes custom objects API client
        self.k8s_custom_api = client.CustomObjectsApi()

        logger.info("JobOrchestrator initialized successfully")
        logger.info(f"  EKS Cluster: {self.eks_cluster}")
        logger.info(f"  Batch Queue: {self.batch_job_queue}")
        logger.info(f"  Batch Job Definition: {self.batch_job_definition}")
        logger.info(f"  K8s Namespace: {self.k8s_namespace}")
        logger.info(f"  S3 Bucket: {self.s3_bucket}")
        logger.info(f"  S3 Metrics Prefix: {self.s3_metrics_prefix}")

    def submit_spark_jobs(
        self,
        count: int,
        scale_factor: int = 10,
        s3_input_prefix: str | None = None,
        s3_output_prefix: str | None = None,
    ) -> list[JobSubmission]:
        """Submit multiple Spark jobs to EKS concurrently.

        Creates SparkApplication custom resources in Kubernetes using the
        Spark Operator. Each job is submitted with a unique name and timestamp.

        Args:
            count: Number of Spark jobs to submit
            scale_factor: TPC-H scale factor (10 or 100)
            s3_input_prefix: S3 prefix for input data (defaults to tpch-sf{scale_factor})
            s3_output_prefix: S3 prefix for output (defaults to results)

        Returns:
            List of JobSubmission objects with creation timestamps

        Raises:
            ApiException: If Kubernetes API call fails
            ValueError: If required configuration is missing
        """
        if not self.eks_cluster:
            raise ValueError("EKS_CLUSTER_NAME not configured")

        if not self.s3_bucket:
            raise ValueError("S3_BUCKET_NAME not configured")

        # Set defaults
        if s3_input_prefix is None:
            s3_input_prefix = f"tpch-sf{scale_factor}"
        if s3_output_prefix is None:
            s3_output_prefix = "results"

        logger.info(f"Submitting {count} Spark jobs to EKS cluster: {self.eks_cluster}")
        logger.info(f"  Scale Factor: {scale_factor}")
        logger.info(f"  S3 Input: s3://{self.s3_bucket}/{s3_input_prefix}")
        logger.info(f"  S3 Output: s3://{self.s3_bucket}/{s3_output_prefix}")

        submissions = []

        for i in range(count):
            # Generate unique job name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            job_name = f"spark-tpch-sf{scale_factor}-{timestamp}-{i:03d}"

            # Record creation time
            created_at = datetime.now()

            try:
                # Create SparkApplication manifest
                spark_app = self._create_spark_application_manifest(
                    job_name=job_name,
                    scale_factor=scale_factor,
                    s3_input_path=f"s3://{self.s3_bucket}/{s3_input_prefix}",
                    s3_output_path=f"s3://{self.s3_bucket}/{s3_output_prefix}",
                )

                # Submit to Kubernetes
                response = self.k8s_custom_api.create_namespaced_custom_object(
                    group="sparkoperator.k8s.io",
                    version="v1beta2",
                    namespace=self.k8s_namespace,
                    plural="sparkapplications",
                    body=spark_app,
                )

                job_id = response["metadata"]["uid"]

                logger.info(
                    f"Submitted Spark job {i+1}/{count}: {job_name} (ID: {job_id})"
                )

                # Create submission record
                submission = JobSubmission(
                    job_id=job_id,
                    job_type="spark",
                    created_at=created_at,
                    job_name=job_name,
                    platform="eks",
                )
                submissions.append(submission)

            except ApiException as e:
                logger.error(f"Failed to submit Spark job {job_name}: {e}")
                logger.error(f"Response body: {e.body}")
                raise

            # Small delay between submissions to avoid overwhelming the API
            if i < count - 1:
                time.sleep(0.5)

        logger.info(f"Successfully submitted {len(submissions)} Spark jobs")
        return submissions

    def _get_resource_config(self, scale_factor: int) -> dict[str, Any]:
        """Get resource configuration based on scale factor.

        Returns matching resources for both Spark and Batch to ensure fair comparison.
        With m6i.xlarge nodes (4 vCPU, 16GB), we can run larger jobs.

        Args:
            scale_factor: TPC-H scale factor

        Returns:
            Dictionary with resource configuration
        """
        if scale_factor == 1:
            return {
                "executor_count": 2,
                "executor_memory": "4g",
                "driver_memory": "2g",
                "batch_vcpu": 4,
                "batch_memory_gb": 8,
            }
        if scale_factor <= 10:
            return {
                "executor_count": 2,  # Reduced to fit in available nodes
                "executor_memory": "4g",
                "driver_memory": "4g",
                "batch_vcpu": 4,
                "batch_memory_gb": 16,
            }
        # scale_factor >= 100
        return {
            "executor_count": 8,
            "executor_memory": "8g",
            "driver_memory": "4g",
            "batch_vcpu": 8,
            "batch_memory_gb": 32,
        }

    def _create_spark_application_manifest(
        self,
        job_name: str,
        scale_factor: int,
        s3_input_path: str,
        s3_output_path: str,
    ) -> dict[str, Any]:
        """Create a SparkApplication manifest for TPC-H benchmark.

        Args:
            job_name: Unique name for the Spark job
            scale_factor: TPC-H scale factor (10 or 100)
            s3_input_path: Full S3 path to input data
            s3_output_path: Full S3 path for output

        Returns:
            Dictionary representing SparkApplication manifest
        """
        # Get resource configuration for this scale factor
        resources = self._get_resource_config(scale_factor)

        executor_count = resources["executor_count"]
        executor_memory = resources["executor_memory"]
        driver_memory = resources["driver_memory"]

        # Get ECR image from environment or use default
        ecr_image = os.getenv(
            "SPARK_ECR_IMAGE",
            "764738119924.dkr.ecr.eu-central-1.amazonaws.com/spark-etl:latest",
        )

        return {
            "apiVersion": "sparkoperator.k8s.io/v1beta2",
            "kind": "SparkApplication",
            "metadata": {
                "name": job_name,
                "namespace": self.k8s_namespace,
                "labels": {
                    "app": "spark-etl",
                    "dataset": "tpch",
                    "data-size": f"sf{scale_factor}",
                    "benchmark": "pythonic-etl",
                    "cost-tracking": "enabled",
                    "orchestrated": "true",
                },
            },
            "spec": {
                "type": "Python",
                "pythonVersion": "3",
                "mode": "cluster",
                "image": ecr_image,
                "imagePullPolicy": "Always",
                "mainApplicationFile": "local:///opt/spark/work-dir/spark_etl_tpch.py",
                "arguments": [
                    "--scale-factor",
                    str(scale_factor),
                    "--output",
                    "/tmp/output",  # noqa: S108
                    "--s3-input",
                    s3_input_path,
                    "--s3-output",
                    s3_output_path,
                ],
                "sparkVersion": "3.5.0",
                "sparkConf": {
                    # S3A Configuration for Pod Identity
                    "spark.hadoop.fs.s3a.impl": (
                        "org.apache.hadoop.fs.s3a.S3AFileSystem"
                    ),
                    "spark.hadoop.fs.s3a.aws.credentials.provider": (
                        "com.amazonaws.auth.DefaultAWSCredentialsProviderChain"
                    ),
                    "spark.hadoop.fs.s3a.endpoint.region": self.aws_region,
                    "spark.driver.extraClassPath": "/opt/spark/jars/hadoop-aws-3.3.4.jar:/opt/spark/jars/aws-java-sdk-bundle-1.12.770.jar",
                    "spark.executor.extraClassPath": "/opt/spark/jars/hadoop-aws-3.3.4.jar:/opt/spark/jars/aws-java-sdk-bundle-1.12.770.jar",
                    "spark.hadoop.fs.s3a.fast.upload": "true",
                    "spark.hadoop.fs.s3a.block.size": "128M",
                    "spark.hadoop.fs.s3a.multipart.size": "128M",
                    "spark.hadoop.fs.s3a.connection.maximum": "50",
                    # Performance tuning
                    "spark.sql.adaptive.enabled": "true",
                    "spark.sql.adaptive.coalescePartitions.enabled": "true",
                    "spark.sql.files.maxPartitionBytes": "134217728",
                    "spark.sql.shuffle.partitions": str(
                        40 if scale_factor <= 10 else 80
                    ),
                    "spark.default.parallelism": str(16 if scale_factor <= 10 else 32),
                    # Memory management
                    "spark.memory.fraction": "0.8",
                    "spark.memory.storageFraction": "0.3",
                    "spark.executor.memoryOverhead": "1024",
                    # Serialization
                    "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
                    # Parquet optimization
                    "spark.sql.parquet.compression.codec": "snappy",
                    "spark.sql.parquet.filterPushdown": "true",
                    "spark.sql.parquet.mergeSchema": "false",
                    # Join optimization
                    "spark.sql.autoBroadcastJoinThreshold": "10485760",
                    "spark.sql.join.preferSortMergeJoin": "true",
                },
                "hadoopConf": {
                    "fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
                    "fs.s3a.aws.credentials.provider": (
                        "com.amazonaws.auth.DefaultAWSCredentialsProviderChain"
                    ),
                },
                "driver": {
                    "cores": 2 if scale_factor > 10 else 1,
                    "coreLimit": "2000m" if scale_factor > 10 else "1000m",
                    "memory": driver_memory,
                    "serviceAccount": "spark-sa",
                    "labels": {
                        "version": "3.5.0",
                        "app": "spark-tpch-driver",
                        "workload": "etl",
                        "data-size": f"sf{scale_factor}",
                        "orchestrated": "true",
                    },
                    "env": [
                        {"name": "AWS_REGION", "value": self.aws_region},
                        {"name": "PYTHONPATH", "value": "/app"},
                        {
                            "name": "BENCHMARK_NAME",
                            "value": f"tpch-query3-sf{scale_factor}",
                        },
                        {"name": "DATA_SIZE", "value": f"sf{scale_factor}"},
                        {"name": "JOB_NAME", "value": job_name},
                    ],
                },
                "executor": {
                    "cores": 2 if scale_factor > 10 else 1,
                    "coreLimit": "2000m" if scale_factor > 10 else "1000m",
                    "memory": executor_memory,
                    "instances": executor_count,
                    "labels": {
                        "version": "3.5.0",
                        "app": "spark-tpch-executor",
                        "workload": "etl",
                        "data-size": f"sf{scale_factor}",
                        "orchestrated": "true",
                    },
                    "env": [
                        {"name": "AWS_REGION", "value": self.aws_region},
                        {"name": "PYTHONPATH", "value": "/app"},
                    ],
                },
                "dynamicAllocation": {"enabled": False},
                "restartPolicy": {"type": "Never"},
                "timeToLiveSeconds": 3600,
            },
        }

    def submit_batch_jobs(
        self,
        count: int,
        scale_factor: int = 10,
        s3_input_prefix: str | None = None,
        s3_output_prefix: str | None = None,
        vcpu: int = 4,
        memory_gb: int = 16,
    ) -> list[JobSubmission]:
        """Submit multiple Polars/DuckDB jobs to AWS Batch concurrently.

        Submits jobs to AWS Batch using the configured job definition and queue.
        Each job runs on Fargate with configurable vCPU and memory.

        Args:
            count: Number of Batch jobs to submit
            scale_factor: TPC-H scale factor (10 or 100)
            s3_input_prefix: S3 prefix for input data (defaults to tpch-sf{scale_factor})
            s3_output_prefix: S3 prefix for output (defaults to results)
            vcpu: Number of vCPUs for each job (default: 4)
            memory_gb: Memory in GB for each job (default: 16)

        Returns:
            List of JobSubmission objects with creation timestamps

        Raises:
            ValueError: If required configuration is missing
            Exception: If AWS Batch API call fails
        """
        if not self.batch_job_queue:
            raise ValueError("BATCH_JOB_QUEUE not configured")

        if not self.batch_job_definition:
            raise ValueError("BATCH_JOB_DEFINITION not configured")

        if not self.s3_bucket:
            raise ValueError("S3_BUCKET_NAME not configured")

        # Set defaults
        if s3_input_prefix is None:
            s3_input_prefix = f"tpch-sf{scale_factor}"
        if s3_output_prefix is None:
            s3_output_prefix = "results"

        logger.info(f"Submitting {count} Batch jobs to queue: {self.batch_job_queue}")
        logger.info(f"  Job Definition: {self.batch_job_definition}")
        logger.info(f"  Scale Factor: {scale_factor}")
        logger.info(f"  S3 Input: s3://{self.s3_bucket}/{s3_input_prefix}")
        logger.info(f"  S3 Output: s3://{self.s3_bucket}/{s3_output_prefix}")
        logger.info(f"  Resources: {vcpu} vCPU, {memory_gb}GB memory")

        submissions = []

        for i in range(count):
            # Generate unique job name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            job_name = f"polars-tpch-sf{scale_factor}-{timestamp}-{i:03d}"

            # Record creation time
            created_at = datetime.now()

            try:
                # Submit job to AWS Batch
                response = self.batch_client.submit_job(
                    jobName=job_name,
                    jobQueue=self.batch_job_queue,
                    jobDefinition=self.batch_job_definition,
                    containerOverrides={
                        "resourceRequirements": [
                            {"type": "VCPU", "value": str(vcpu)},
                            {"type": "MEMORY", "value": str(memory_gb * 1024)},
                        ],
                        "environment": [
                            {"name": "SCALE_FACTOR", "value": str(scale_factor)},
                            {"name": "S3_BUCKET", "value": self.s3_bucket},
                            {"name": "S3_INPUT_PREFIX", "value": s3_input_prefix},
                            {"name": "S3_OUTPUT_PREFIX", "value": s3_output_prefix},
                            {"name": "AWS_REGION", "value": self.aws_region},
                            {"name": "JOB_NAME", "value": job_name},
                            {
                                "name": "BENCHMARK_NAME",
                                "value": f"tpch-query3-sf{scale_factor}",
                            },
                        ],
                    },
                    tags={
                        "app": "polars-etl",
                        "dataset": "tpch",
                        "data-size": f"sf{scale_factor}",
                        "benchmark": "pythonic-etl",
                        "cost-tracking": "enabled",
                        "orchestrated": "true",
                    },
                )

                job_id = response["jobId"]

                logger.info(
                    f"Submitted Batch job {i+1}/{count}: {job_name} (ID: {job_id})"
                )

                # Create submission record
                submission = JobSubmission(
                    job_id=job_id,
                    job_type="polars",
                    created_at=created_at,
                    job_name=job_name,
                    platform="batch",
                )
                submissions.append(submission)

            except Exception as e:
                logger.error(f"Failed to submit Batch job {job_name}: {e}")
                raise

            # Small delay between submissions to avoid overwhelming the API
            if i < count - 1:
                time.sleep(0.5)

        logger.info(f"Successfully submitted {len(submissions)} Batch jobs")
        return submissions

    def monitor_jobs(
        self,
        submissions: list[JobSubmission],
        poll_interval: int = 5,
        max_wait_time: int = 3600,
    ) -> list[JobMetrics]:
        """Monitor job execution and collect metrics with timestamps.

        Polls job status every poll_interval seconds and records:
        - Job Started timestamp (when execution begins)
        - Job Completed timestamp (when finished)
        - Startup latency (started - created)

        Args:
            submissions: List of JobSubmission objects to monitor
            poll_interval: Seconds between status checks (default: 5)
            max_wait_time: Maximum seconds to wait for all jobs (default: 3600)

        Returns:
            List of JobMetrics with complete timing information

        Raises:
            TimeoutError: If jobs don't complete within max_wait_time
        """
        logger.info(f"Monitoring {len(submissions)} jobs")
        logger.info(f"  Poll interval: {poll_interval}s")
        logger.info(f"  Max wait time: {max_wait_time}s")

        # Initialize metrics for each job
        metrics_map: dict[str, JobMetrics] = {}
        for submission in submissions:
            metrics_map[submission.job_id] = JobMetrics(
                job_id=submission.job_id,
                job_type=submission.job_type,
                job_name=submission.job_name,
                platform=submission.platform,
                created_at=submission.created_at,
                started_at=None,
                completed_at=None,
                startup_latency_seconds=None,
                execution_time_seconds=None,
                status="PENDING",
            )

        start_time = time.time()
        completed_jobs = set()

        while len(completed_jobs) < len(submissions):
            # Check if we've exceeded max wait time
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                logger.error(
                    f"Timeout: {len(completed_jobs)}/{len(submissions)} jobs completed"
                    f" after {elapsed:.0f}s"
                )
                raise TimeoutError(
                    f"Jobs did not complete within {max_wait_time}s. "
                    f"Completed: {len(completed_jobs)}/{len(submissions)}"
                )

            # Poll status for each job
            for submission in submissions:
                if submission.job_id in completed_jobs:
                    continue

                metrics = metrics_map[submission.job_id]

                try:
                    if submission.platform == "eks":
                        status_info = self._get_spark_job_status(submission.job_name)
                    else:  # batch
                        status_info = self._get_batch_job_status(submission.job_id)

                    # Update metrics based on status
                    old_status = metrics.status
                    metrics.status = status_info["status"]

                    # Record started timestamp on transition to RUNNING
                    if old_status != "RUNNING" and metrics.status == "RUNNING":
                        metrics.started_at = datetime.now()
                        logger.info(
                            f"Job {submission.job_name} started (startup latency: "
                            f"{(metrics.started_at - metrics.created_at).total_seconds():.1f}s)"
                        )

                    # Record completed timestamp on transition to terminal state
                    if (
                        metrics.status in ["SUCCEEDED", "FAILED"]
                        and submission.job_id not in completed_jobs
                    ):
                        metrics.completed_at = datetime.now()
                        completed_jobs.add(submission.job_id)

                        # Calculate execution time if we have started timestamp
                        if metrics.started_at:
                            metrics.execution_time_seconds = (
                                metrics.completed_at - metrics.started_at
                            ).total_seconds()

                        logger.info(
                            f"Job {submission.job_name} {metrics.status.lower()} (execution"
                            f" time: {metrics.execution_time_seconds:.1f}s)"
                        )

                except Exception as e:
                    logger.error(
                        f"Error checking status for job {submission.job_name}: {e}"
                    )

            # Log progress
            if len(completed_jobs) > 0:
                logger.info(
                    f"Progress: {len(completed_jobs)}/{len(submissions)} jobs completed"
                    f" ({elapsed:.0f}s elapsed)"
                )

            # Wait before next poll
            if len(completed_jobs) < len(submissions):
                time.sleep(poll_interval)

        logger.info(f"All {len(submissions)} jobs completed in {elapsed:.0f}s")

        # Return metrics as list
        return list(metrics_map.values())

    def _get_spark_job_status(self, job_name: str) -> dict[str, Any]:
        """Get status of a Spark job from Kubernetes.

        Args:
            job_name: Name of the SparkApplication

        Returns:
            Dictionary with 'status' key (PENDING, RUNNING, SUCCEEDED, FAILED)
        """
        try:
            response = self.k8s_custom_api.get_namespaced_custom_object(
                group="sparkoperator.k8s.io",
                version="v1beta2",
                namespace=self.k8s_namespace,
                plural="sparkapplications",
                name=job_name,
            )

            # Extract application state from status
            app_state = response.get("status", {}).get("applicationState", {})
            state = app_state.get("state", "PENDING")

            # Map Spark states to our standard states
            status_map = {
                "": "PENDING",
                "SUBMITTED": "PENDING",
                "RUNNING": "RUNNING",
                "COMPLETED": "SUCCEEDED",
                "FAILED": "FAILED",
                "SUBMISSION_FAILED": "FAILED",
                "PENDING_RERUN": "PENDING",
                "INVALIDATING": "FAILED",
                "SUCCEEDING": "RUNNING",
                "FAILING": "RUNNING",
                "UNKNOWN": "PENDING",
            }

            mapped_status = status_map.get(state, "PENDING")

        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Spark job {job_name} not found")
                return {"status": "FAILED", "raw_state": "NOT_FOUND"}
            # Re-raise for other API exceptions
            logger.error(f"Error getting Spark job status: {e}")
            raise
        else:
            return {"status": mapped_status, "raw_state": state}

    def _get_batch_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of an AWS Batch job.

        Args:
            job_id: AWS Batch job ID

        Returns:
            Dictionary with 'status' key (PENDING, RUNNING, SUCCEEDED, FAILED)
        """
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])

            if not response["jobs"]:
                logger.warning(f"Batch job {job_id} not found")
                return {"status": "FAILED", "raw_state": "NOT_FOUND"}

            job = response["jobs"][0]
            status = job["status"]

            # Map Batch states to our standard states
            status_map = {
                "SUBMITTED": "PENDING",
                "PENDING": "PENDING",
                "RUNNABLE": "PENDING",
                "STARTING": "PENDING",
                "RUNNING": "RUNNING",
                "SUCCEEDED": "SUCCEEDED",
                "FAILED": "FAILED",
            }

            mapped_status = status_map.get(status, "PENDING")

        except Exception as e:
            logger.error(f"Error getting Batch job status: {e}")
            raise
        return {"status": mapped_status, "raw_state": status}

    def calculate_startup_latency(self, metrics: list[JobMetrics]) -> list[JobMetrics]:
        """Calculate startup latency for all jobs.

        Computes the delta between job creation and execution start:
        startup_latency = started_at - created_at

        Validates that latency is non-negative and updates metrics in place.

        Args:
            metrics: List of JobMetrics objects

        Returns:
            Updated list of JobMetrics with startup_latency_seconds populated

        Raises:
            ValueError: If startup latency is negative (invalid timestamps)
        """
        logger.info(f"Calculating startup latency for {len(metrics)} jobs")

        for metric in metrics:
            if metric.started_at and metric.created_at:
                # Calculate latency
                latency = (metric.started_at - metric.created_at).total_seconds()

                # Validate non-negative
                if latency < 0:
                    logger.error(
                        f"Invalid timestamps for job {metric.job_name}: started_at"
                        f" ({metric.started_at}) < created_at ({metric.created_at})"
                    )
                    raise ValueError(
                        f"Negative startup latency for job {metric.job_name}:"
                        f" {latency}s"
                    )

                metric.startup_latency_seconds = latency

                logger.debug(f"Job {metric.job_name}: startup latency = {latency:.2f}s")
            else:
                logger.warning(
                    f"Job {metric.job_name}: missing timestamps "
                    f"(created_at={metric.created_at}, started_at={metric.started_at})"
                )
                metric.startup_latency_seconds = None

        # Calculate statistics
        valid_latencies = [
            m.startup_latency_seconds
            for m in metrics
            if m.startup_latency_seconds is not None
        ]

        if valid_latencies:
            avg_latency = sum(valid_latencies) / len(valid_latencies)
            min_latency = min(valid_latencies)
            max_latency = max(valid_latencies)

            logger.info("Startup latency statistics:")
            logger.info(f"  Average: {avg_latency:.2f}s")
            logger.info(f"  Min: {min_latency:.2f}s")
            logger.info(f"  Max: {max_latency:.2f}s")
            logger.info(
                f"  Jobs with valid latency: {len(valid_latencies)}/{len(metrics)}"
            )
        else:
            logger.warning("No valid startup latency data available")

        return metrics

    def collect_metrics_from_s3(self, metrics: list[JobMetrics]) -> list[JobMetrics]:
        """Collect execution metrics from S3 for all completed jobs.

        Downloads metrics JSON files from S3 and enriches JobMetrics with:
        - peak_memory_mb
        - bytes_read
        - bytes_written
        - Additional execution details

        Args:
            metrics: List of JobMetrics with timing information

        Returns:
            Updated list of JobMetrics with execution metrics from S3

        Note:
            If a metrics file is not found or invalid, logs a warning and continues.
            The job's timing metrics are preserved even if S3 metrics are missing.
        """
        logger.info(f"Collecting execution metrics from S3 for {len(metrics)} jobs")

        if not self.s3_bucket:
            logger.warning(
                "S3_BUCKET_NAME not configured - skipping metrics collection"
            )
            return metrics

        for metric in metrics:
            # Only collect metrics for completed jobs
            if metric.status not in ["SUCCEEDED", "FAILED"]:
                logger.debug(
                    f"Skipping metrics collection for job {metric.job_name} "
                    f"(status: {metric.status})"
                )
                continue

            try:
                # Construct S3 key for metrics file
                # Expected format: s3://bucket/metrics/{job_name}/metrics.json
                metrics_key = f"{self.s3_metrics_prefix}/{metric.job_name}/metrics.json"

                logger.debug(
                    f"Downloading metrics for {metric.job_name} from "
                    f"s3://{self.s3_bucket}/{metrics_key}"
                )

                # Download metrics file from S3
                response = self.s3_client.get_object(
                    Bucket=self.s3_bucket, Key=metrics_key
                )
                metrics_data = json.loads(response["Body"].read().decode("utf-8"))

                # Extract metrics and update JobMetrics object
                metric.peak_memory_mb = metrics_data.get("peak_memory_mb")
                metric.bytes_read = metrics_data.get("bytes_read")
                metric.bytes_written = metrics_data.get("bytes_written")

                # If execution time is in S3 metrics but not calculated, use it
                if (
                    not metric.execution_time_seconds
                    and "execution_time_seconds" in metrics_data
                ):
                    metric.execution_time_seconds = metrics_data[
                        "execution_time_seconds"
                    ]

                logger.info(
                    f"Collected metrics for {metric.job_name}: "
                    f"memory={metric.peak_memory_mb}MB, "
                    f"read={metric.bytes_read}, "
                    f"written={metric.bytes_written}"
                )

            except self.s3_client.exceptions.NoSuchKey:
                logger.warning(
                    f"Metrics file not found for job {metric.job_name} at "
                    f"s3://{self.s3_bucket}/{metrics_key}"
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON in metrics file for job {metric.job_name}: {e}"
                )
            except Exception as e:
                logger.error(f"Error collecting metrics for job {metric.job_name}: {e}")

        # Log summary
        metrics_collected = sum(1 for m in metrics if m.peak_memory_mb is not None)
        logger.info(
            f"Metrics collection complete: {metrics_collected}/{len(metrics)} jobs "
            "have execution metrics"
        )

        return metrics

    def save_aggregated_metrics(
        self, metrics: list[JobMetrics], output_path: str
    ) -> None:
        """Save aggregated metrics to a JSON file.

        Args:
            metrics: List of JobMetrics to save
            output_path: Local file path or S3 path (s3://bucket/key)

        Raises:
            IOError: If file write fails
        """
        logger.info(f"Saving aggregated metrics to {output_path}")

        # Convert metrics to dictionaries
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "total_jobs": len(metrics),
            "jobs": [m.to_dict() for m in metrics],
            "summary": self._calculate_summary_statistics(metrics),
        }

        # Determine if output is S3 or local
        if output_path.startswith("s3://"):
            # Parse S3 path
            parts = output_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else "metrics.json"

            # Upload to S3
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(metrics_data, indent=2),
                ContentType="application/json",
            )
            logger.info(f"Metrics saved to S3: s3://{bucket}/{key}")
        else:
            # Save to local file
            with open(output_path, "w") as f:
                json.dump(metrics_data, f, indent=2)
            logger.info(f"Metrics saved to local file: {output_path}")

    def _calculate_summary_statistics(
        self, metrics: list[JobMetrics]
    ) -> dict[str, Any]:
        """Calculate summary statistics across all jobs.

        Args:
            metrics: List of JobMetrics

        Returns:
            Dictionary with summary statistics by job type and platform
        """
        summary = {
            "by_type": {},
            "by_platform": {},
            "overall": {},
        }

        # Group by job type
        for job_type in ["spark", "polars"]:
            type_metrics = [m for m in metrics if m.job_type == job_type]
            if type_metrics:
                summary["by_type"][job_type] = self._calculate_stats_for_group(
                    type_metrics
                )

        # Group by platform
        for platform in ["eks", "batch"]:
            platform_metrics = [m for m in metrics if m.platform == platform]
            if platform_metrics:
                summary["by_platform"][platform] = self._calculate_stats_for_group(
                    platform_metrics
                )

        # Overall statistics
        summary["overall"] = self._calculate_stats_for_group(metrics)

        return summary

    def _calculate_stats_for_group(self, metrics: list[JobMetrics]) -> dict[str, Any]:
        """Calculate statistics for a group of metrics.

        Args:
            metrics: List of JobMetrics

        Returns:
            Dictionary with mean, median, min, max for key metrics
        """
        if not metrics:
            return {}

        # Extract values
        startup_latencies = [
            m.startup_latency_seconds
            for m in metrics
            if m.startup_latency_seconds is not None
        ]
        execution_times = [
            m.execution_time_seconds
            for m in metrics
            if m.execution_time_seconds is not None
        ]
        memory_values = [
            m.peak_memory_mb for m in metrics if m.peak_memory_mb is not None
        ]

        stats = {
            "count": len(metrics),
            "succeeded": sum(1 for m in metrics if m.status == "SUCCEEDED"),
            "failed": sum(1 for m in metrics if m.status == "FAILED"),
        }

        # Startup latency stats
        if startup_latencies:
            stats["startup_latency"] = {
                "mean": sum(startup_latencies) / len(startup_latencies),
                "min": min(startup_latencies),
                "max": max(startup_latencies),
                "count": len(startup_latencies),
            }

        # Execution time stats
        if execution_times:
            stats["execution_time"] = {
                "mean": sum(execution_times) / len(execution_times),
                "min": min(execution_times),
                "max": max(execution_times),
                "count": len(execution_times),
            }

        # Memory stats
        if memory_values:
            stats["peak_memory_mb"] = {
                "mean": sum(memory_values) / len(memory_values),
                "min": min(memory_values),
                "max": max(memory_values),
                "count": len(memory_values),
            }

        return stats


# Example usage
if __name__ == "__main__":
    # Initialize orchestrator
    orchestrator = JobOrchestrator()

    # Submit jobs
    logger.info("Submitting jobs...")
    spark_jobs = orchestrator.submit_spark_jobs(count=2, scale_factor=10)
    batch_jobs = orchestrator.submit_batch_jobs(count=2, scale_factor=10)

    # Combine all submissions
    all_jobs = spark_jobs + batch_jobs

    # Monitor jobs
    logger.info("Monitoring jobs...")
    metrics = orchestrator.monitor_jobs(all_jobs)

    # Calculate startup latency
    logger.info("Calculating startup latency...")
    metrics = orchestrator.calculate_startup_latency(metrics)

    # Collect metrics from S3
    logger.info("Collecting metrics from S3...")
    metrics = orchestrator.collect_metrics_from_s3(metrics)

    # Save aggregated metrics
    output_path = "orchestration_metrics.json"
    orchestrator.save_aggregated_metrics(metrics, output_path)

    logger.info("Orchestration complete!")
