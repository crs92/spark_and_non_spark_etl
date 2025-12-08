#!/usr/bin/env python3
"""Full benchmark orchestration script.

This script orchestrates the execution of benchmarks across both EC2 (Polars)
and EKS (Spark) environments, collecting metrics and storing results in S3.

Usage:
    python scripts/run_full_benchmark.py --sizes tiny,small,medium
    python scripts/run_full_benchmark.py --ec2-only --sizes tiny,small
    python scripts/run_full_benchmark.py --eks-only --sizes medium,large
"""

# ruff: noqa: S603, S607
# S603/S607: subprocess calls are intentional for AWS CLI and kubectl


import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    data_size: str
    environment: str  # 'ec2' or 'eks'
    timestamp: str
    instance_type: str | None = None
    executor_count: int | None = None


@dataclass
class BenchmarkResult:
    """Results from a benchmark execution."""

    config: BenchmarkConfig
    success: bool
    execution_time: float
    error_message: str | None = None
    metrics_file: str | None = None
    results_file: str | None = None
    cloudwatch_metrics: dict[str, Any] | None = None


class BenchmarkOrchestrator:
    """Orchestrates benchmark execution across EC2 and EKS."""

    @staticmethod
    def _raise_terraform_error(stderr: str) -> None:
        """Raise error for Terraform failures."""
        raise RuntimeError(f"Failed to get instance ID from Terraform: {stderr}")

    @staticmethod
    def _raise_ssm_error(stderr: str) -> None:
        """Raise error for SSM command failures."""
        raise RuntimeError(f"Failed to send SSM command: {stderr}")

    @staticmethod
    def _raise_timeout_error(max_wait: int) -> None:
        """Raise error for command timeout."""
        raise RuntimeError(f"Command timed out after {max_wait}s")

    @staticmethod
    def _raise_manifest_error(manifest_path: Path) -> None:
        """Raise error for missing manifest."""
        raise FileNotFoundError(f"Spark manifest not found: {manifest_path}")

    @staticmethod
    def _raise_kubectl_error(stderr: str) -> None:
        """Raise error for kubectl failures."""
        raise RuntimeError(f"Failed to apply manifest: {stderr}")

    def __init__(
        self,
        data_sizes: list[str],
        run_ec2: bool = True,
        run_eks: bool = True,
        aws_region: str = "eu-central-1",
        results_dir: str = "benchmark_results",
    ):
        """Initialize the orchestrator.

        Args:
            data_sizes: List of data sizes to benchmark
            run_ec2: Whether to run EC2 benchmarks
            run_eks: Whether to run EKS benchmarks
            aws_region: AWS region for resources
            results_dir: Directory to store results
        """
        self.data_sizes = data_sizes
        self.run_ec2 = run_ec2
        self.run_eks = run_eks
        self.aws_region = aws_region
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # AWS clients
        self.ec2_client = boto3.client("ec2", region_name=aws_region)
        self.eks_client = boto3.client("eks", region_name=aws_region)
        self.s3_client = boto3.client("s3", region_name=aws_region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=aws_region)

        # Results tracking
        self.results: list[BenchmarkResult] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info("=" * 60)
        logger.info("Benchmark Orchestrator Initialized")
        logger.info("=" * 60)
        logger.info("Data Sizes: %s", ", ".join(data_sizes))
        logger.info("Run EC2: %s", run_ec2)
        logger.info("Run EKS: %s", run_eks)
        logger.info("AWS Region: %s", aws_region)
        logger.info("Results Directory: %s", self.results_dir)
        logger.info("=" * 60)

    def discover_infrastructure(self) -> dict[str, Any]:
        """Discover existing infrastructure resources.

        Returns:
            Dictionary with infrastructure details
        """
        logger.info("Discovering infrastructure...")

        infra = {
            "ec2_instance": None,
            "eks_cluster": None,
            "s3_bucket": None,
        }

        # Find EC2 instance
        if self.run_ec2:
            try:
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Project", "Values": ["etl-benchmark"]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "stopped"],
                        },
                    ]
                )

                if response["Reservations"]:
                    instance = response["Reservations"][0]["Instances"][0]
                    infra["ec2_instance"] = {
                        "instance_id": instance["InstanceId"],
                        "instance_type": instance["InstanceType"],
                        "public_ip": instance.get("PublicIpAddress"),
                        "private_ip": instance.get("PrivateIpAddress"),
                        "state": instance["State"]["Name"],
                    }
                    logger.info(
                        "Found EC2 instance: %s (%s) - State: %s",
                        infra["ec2_instance"]["instance_id"],
                        infra["ec2_instance"]["instance_type"],
                        infra["ec2_instance"]["state"],
                    )
                else:
                    logger.warning("No EC2 instance found")
            except Exception as e:
                logger.error("Error discovering EC2 instance: %s", e)

        # Find EKS cluster
        if self.run_eks:
            try:
                clusters = self.eks_client.list_clusters()
                for cluster_name in clusters.get("clusters", []):
                    if "etl-benchmark" in cluster_name.lower():
                        cluster_info = self.eks_client.describe_cluster(
                            name=cluster_name
                        )
                        infra["eks_cluster"] = {
                            "name": cluster_name,
                            "endpoint": cluster_info["cluster"]["endpoint"],
                            "status": cluster_info["cluster"]["status"],
                        }
                        logger.info("Found EKS cluster: %s", cluster_name)
                        break

                if not infra["eks_cluster"]:
                    logger.warning("No EKS cluster found")
            except Exception as e:
                logger.error("Error discovering EKS cluster: %s", e)

        # Find S3 bucket
        try:
            buckets = self.s3_client.list_buckets()
            for bucket in buckets.get("Buckets", []):
                if "etl-benchmark" in bucket["Name"]:
                    infra["s3_bucket"] = bucket["Name"]
                    logger.info("Found S3 bucket: %s", bucket["Name"])
                    break

            if not infra["s3_bucket"]:
                logger.warning("No S3 bucket found")
        except Exception as e:
            logger.error("Error discovering S3 bucket: %s", e)

        return infra

    def run_ec2_benchmark(
        self, data_size: str, instance_info: dict[str, Any]
    ) -> BenchmarkResult:
        """Run benchmark on EC2 instance.

        Args:
            data_size: Size of dataset to process
            instance_info: EC2 instance information

        Returns:
            BenchmarkResult with execution details
        """
        logger.info("=" * 60)
        logger.info("Running EC2 Benchmark: %s", data_size)
        logger.info("=" * 60)

        config = BenchmarkConfig(
            data_size=data_size,
            environment="ec2",
            timestamp=self.timestamp,
            instance_type=instance_info["instance_type"],
        )

        start_time = time.time()

        try:
            # Get instance ID from Terraform
            logger.info("Getting instance ID from Terraform...")
            terraform_dir = Path(__file__).parent.parent / "terraform"

            instance_id_result = subprocess.run(
                ["/usr/bin/terraform", "output", "-raw", "ec2_instance_id"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            if instance_id_result.returncode != 0:
                self._raise_terraform_error(instance_id_result.stderr)

            instance_id = instance_id_result.stdout.strip()

            # Ensure instance is running
            if instance_info.get("state") != "running":
                logger.info("Starting EC2 instance...")
                self.ec2_client.start_instances(InstanceIds=[instance_id])
                waiter = self.ec2_client.get_waiter("instance_running")
                waiter.wait(InstanceIds=[instance_id])
                logger.info("Instance started successfully")

            # Build the remote command to run the benchmark using Docker
            remote_cmd = f"/usr/local/bin/run-polars-benchmark.sh {data_size}"

            # Use AWS Systems Manager Session Manager to execute command
            logger.info("Executing via SSM on instance %s: %s", instance_id, remote_cmd)

            result = subprocess.run(
                [
                    "/usr/local/bin/aws",
                    "ssm",
                    "send-command",
                    "--instance-ids",
                    instance_id,
                    "--document-name",
                    "AWS-RunShellScript",
                    "--parameters",
                    f'commands=["{remote_cmd}"]',
                    "--region",
                    self.aws_region,
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self._raise_ssm_error(result.stderr)

            # Parse command ID from response
            import json

            response = json.loads(result.stdout)
            command_id = response["Command"]["CommandId"]

            logger.info("SSM Command ID: %s", command_id)
            logger.info("Waiting for command to complete...")

            # Wait for command to complete
            max_wait = 1800  # 30 minutes (increased for data download + processing)
            poll_interval = 10
            elapsed = 0

            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval

                # Check command status
                status_result = subprocess.run(
                    [
                        "/usr/local/bin/aws",
                        "ssm",
                        "get-command-invocation",
                        "--command-id",
                        command_id,
                        "--instance-id",
                        instance_id,
                        "--region",
                        self.aws_region,
                        "--output",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if status_result.returncode == 0:
                    status_response = json.loads(status_result.stdout)
                    status = status_response["Status"]

                    if status == "Success":
                        logger.info("Command completed successfully")
                        result.stdout = status_response.get("StandardOutputContent", "")
                        result.stderr = status_response.get("StandardErrorContent", "")
                        result.returncode = 0
                        break
                    if status in ["Failed", "Cancelled", "TimedOut"]:
                        logger.error("Command failed with status: %s", status)
                        result.stdout = status_response.get("StandardOutputContent", "")
                        result.stderr = status_response.get("StandardErrorContent", "")
                        result.returncode = 1
                        break
                    logger.info("Command status: %s (elapsed: %ds)", status, elapsed)

            if elapsed >= max_wait:
                self._raise_timeout_error(max_wait)

            execution_time = time.time() - start_time

            if result.returncode == 0:
                logger.info(
                    "EC2 benchmark completed successfully in %.2fs", execution_time
                )
                logger.info(
                    "Output: %s",
                    result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
                )

                return BenchmarkResult(
                    config=config,
                    success=True,
                    execution_time=execution_time,
                )

            logger.error("EC2 benchmark failed: %s", result.stderr)
            return BenchmarkResult(
                config=config,
                success=False,
                execution_time=execution_time,
                error_message=result.stderr,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error("Error running EC2 benchmark: %s", e)
            return BenchmarkResult(
                config=config,
                success=False,
                execution_time=execution_time,
                error_message=str(e),
            )

    def run_eks_benchmark(
        self, data_size: str, cluster_info: dict[str, Any]
    ) -> BenchmarkResult:
        """Run benchmark on EKS cluster.

        Args:
            data_size: Size of dataset to process
            cluster_info: EKS cluster information

        Returns:
            BenchmarkResult with execution details
        """
        logger.info("=" * 60)
        logger.info("Running EKS Benchmark: %s", data_size)
        logger.info("=" * 60)

        # Determine executor count based on data size
        executor_counts = {
            "tiny": 2,
            "small": 3,
            "medium": 5,
            "large": 10,
            "xlarge": 20,
            "xxlarge": 30,
        }
        executor_count = executor_counts.get(data_size, 3)

        config = BenchmarkConfig(
            data_size=data_size,
            environment="eks",
            timestamp=self.timestamp,
            executor_count=executor_count,
        )

        start_time = time.time()

        try:
            # Find the SparkApplication manifest
            manifest_path = Path(f"k8s/spark-nyc-taxi-{data_size}.yaml")

            if not manifest_path.exists():
                self._raise_manifest_error(manifest_path)

            # Apply the manifest
            logger.info("Applying SparkApplication manifest: %s", manifest_path)
            result = subprocess.run(
                ["/usr/local/bin/kubectl", "apply", "-f", str(manifest_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self._raise_kubectl_error(result.stderr)

            # Wait for completion
            app_name = f"spark-nyc-taxi-{data_size}"
            logger.info("Waiting for SparkApplication to complete: %s", app_name)

            max_wait = 3600  # 1 hour timeout
            poll_interval = 30
            elapsed = 0

            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval

                # Check application status
                result = subprocess.run(
                    [
                        "/usr/local/bin/kubectl",
                        "get",
                        "sparkapplication",
                        app_name,
                        "-o",
                        "jsonpath={.status.applicationState.state}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    state = result.stdout.strip()
                    logger.info("Application state: %s (elapsed: %ds)", state, elapsed)

                    if state == "COMPLETED":
                        execution_time = time.time() - start_time
                        logger.info(
                            "EKS benchmark completed successfully in %.2fs",
                            execution_time,
                        )

                        return BenchmarkResult(
                            config=config,
                            success=True,
                            execution_time=execution_time,
                        )
                    if state in ["FAILED", "SUBMISSION_FAILED"]:
                        execution_time = time.time() - start_time
                        logger.error("EKS benchmark failed with state: %s", state)

                        # Get logs
                        logs_result = subprocess.run(
                            ["/usr/local/bin/kubectl", "logs", f"{app_name}-driver"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )

                        return BenchmarkResult(
                            config=config,
                            success=False,
                            execution_time=execution_time,
                            error_message=f"State: {state}\nLogs: {logs_result.stdout}",
                        )

            # Timeout
            execution_time = time.time() - start_time
            logger.error("EKS benchmark timed out after %ds", max_wait)
            return BenchmarkResult(
                config=config,
                success=False,
                execution_time=execution_time,
                error_message=f"Timeout after {max_wait}s",
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error("Error running EKS benchmark: %s", e)
            return BenchmarkResult(
                config=config,
                success=False,
                execution_time=execution_time,
                error_message=str(e),
            )

    def _find_latest_file(self, prefix: str, suffix: str) -> Path | None:
        """Find the latest file matching prefix and suffix.

        Args:
            prefix: File prefix to match
            suffix: File suffix to match

        Returns:
            Path to latest file or None
        """
        matching_files = list(self.results_dir.glob(f"{prefix}*{suffix}"))
        if matching_files:
            return max(matching_files, key=lambda p: p.stat().st_mtime)
        return None

    def run_all_benchmarks(self) -> list[BenchmarkResult]:
        """Run all configured benchmarks.

        Returns:
            List of BenchmarkResult objects
        """
        logger.info("=" * 60)
        logger.info("Starting Full Benchmark Suite")
        logger.info("=" * 60)

        # Discover infrastructure
        infra = self.discover_infrastructure()

        # Validate infrastructure
        if self.run_ec2 and not infra["ec2_instance"]:
            logger.error("EC2 benchmarks requested but no instance found")
            self.run_ec2 = False

        if self.run_eks and not infra["eks_cluster"]:
            logger.error("EKS benchmarks requested but no cluster found")
            self.run_eks = False

        if not self.run_ec2 and not self.run_eks:
            logger.error("No valid infrastructure found for benchmarks")
            return []

        # Run benchmarks for each data size
        for data_size in self.data_sizes:
            logger.info("\n" + "=" * 60)
            logger.info("Benchmarking Data Size: %s", data_size)
            logger.info("=" * 60)

            # Run EC2 benchmark
            if self.run_ec2:
                result = self.run_ec2_benchmark(data_size, infra["ec2_instance"])
                self.results.append(result)

                # Wait between benchmarks
                if self.run_eks:
                    logger.info("Waiting 60s before next benchmark...")
                    time.sleep(60)

            # Run EKS benchmark
            if self.run_eks:
                result = self.run_eks_benchmark(data_size, infra["eks_cluster"])
                self.results.append(result)

                # Wait between benchmarks
                if data_size != self.data_sizes[-1]:
                    logger.info("Waiting 60s before next benchmark...")
                    time.sleep(60)

        return self.results

    def save_results(self) -> str:
        """Save all benchmark results to a JSON file.

        Returns:
            Path to results file
        """
        results_file = (
            self.results_dir / f"full_benchmark_results_{self.timestamp}.json"
        )

        results_data = {
            "timestamp": self.timestamp,
            "data_sizes": self.data_sizes,
            "run_ec2": self.run_ec2,
            "run_eks": self.run_eks,
            "aws_region": self.aws_region,
            "results": [
                {
                    "config": asdict(r.config),
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "error_message": r.error_message,
                    "metrics_file": r.metrics_file,
                    "results_file": r.results_file,
                }
                for r in self.results
            ],
        }

        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        logger.info("Results saved to: %s", results_file)
        return str(results_file)

    def print_summary(self):
        """Print a summary of all benchmark results."""
        logger.info("\n" + "=" * 60)
        logger.info("Benchmark Summary")
        logger.info("=" * 60)

        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful

        logger.info("Total Benchmarks: %d", len(self.results))
        logger.info("Successful: %d", successful)
        logger.info("Failed: %d", failed)
        logger.info("")

        # Group by environment
        ec2_results = [r for r in self.results if r.config.environment == "ec2"]
        eks_results = [r for r in self.results if r.config.environment == "eks"]

        if ec2_results:
            logger.info("EC2 (Polars) Results:")
            for result in ec2_results:
                status = "✓" if result.success else "✗"
                logger.info(
                    "  %s %s: %.2fs",
                    status,
                    result.config.data_size,
                    result.execution_time,
                )

        if eks_results:
            logger.info("")
            logger.info("EKS (Spark) Results:")
            for result in eks_results:
                status = "✓" if result.success else "✗"
                logger.info(
                    "  %s %s: %.2fs",
                    status,
                    result.config.data_size,
                    result.execution_time,
                )

        logger.info("=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Full benchmark orchestration for EC2 and EKS"
    )
    parser.add_argument(
        "--sizes",
        type=str,
        default="tiny,small",
        help="Comma-separated list of data sizes (default: tiny,small)",
    )
    parser.add_argument(
        "--ec2-only",
        action="store_true",
        help="Run only EC2 benchmarks",
    )
    parser.add_argument(
        "--eks-only",
        action="store_true",
        help="Run only EKS benchmarks",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="eu-central-1",
        help="AWS region (default: eu-central-1)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="benchmark_results",
        help="Directory for results (default: benchmark_results)",
    )

    args = parser.parse_args()

    # Parse data sizes
    data_sizes = [s.strip() for s in args.sizes.split(",")]

    # Validate data sizes
    valid_sizes = ["tiny", "small", "medium", "large", "xlarge", "xxlarge"]
    for size in data_sizes:
        if size not in valid_sizes:
            logger.error("Invalid data size: %s", size)
            logger.error("Valid sizes: %s", ", ".join(valid_sizes))
            sys.exit(1)

    # Determine which environments to run
    run_ec2 = not args.eks_only
    run_eks = not args.ec2_only

    # Create orchestrator
    orchestrator = BenchmarkOrchestrator(
        data_sizes=data_sizes,
        run_ec2=run_ec2,
        run_eks=run_eks,
        aws_region=args.region,
        results_dir=args.results_dir,
    )

    # Run benchmarks
    try:
        orchestrator.run_all_benchmarks()

        # Save results
        results_file = orchestrator.save_results()

        # Print summary
        orchestrator.print_summary()

        logger.info("\nResults saved to: %s", results_file)
        logger.info("\nNext steps:")
        logger.info(
            "1. Collect CloudWatch metrics: python"
            " scripts/collect_cloudwatch_metrics.py"
        )
        logger.info("2. Validate results: python scripts/validate_results.py")
        logger.info("3. Generate report: python scripts/generate_benchmark_report.py")

    except KeyboardInterrupt:
        logger.warning("\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Benchmark failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
