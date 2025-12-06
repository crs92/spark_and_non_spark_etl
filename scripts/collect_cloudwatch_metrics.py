#!/usr/bin/env python3
"""CloudWatch metrics collection script.

This script collects metrics from CloudWatch for both EC2 and EKS benchmarks,
including CPU, memory, network, and disk I/O metrics.

Usage:
    python scripts/collect_cloudwatch_metrics.py --benchmark-id 20241205_120000
    python scripts/collect_cloudwatch_metrics.py --ec2-instance i-1234567890abcdef0
    python scripts/collect_cloudwatch_metrics.py --eks-cluster etl-benchmark-cluster
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
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
class MetricStatistics:
    """Statistics for a CloudWatch metric."""

    metric_name: str
    unit: str
    average: float | None = None
    maximum: float | None = None
    minimum: float | None = None
    sum: float | None = None
    sample_count: int = 0
    datapoints: list[dict[str, Any]] | None = None


@dataclass
class ResourceMetrics:
    """Metrics for a resource (EC2 instance or EKS pod)."""

    resource_id: str
    resource_type: str  # 'ec2' or 'eks'
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    metrics: dict[str, MetricStatistics]


class CloudWatchMetricsCollector:
    """Collects metrics from CloudWatch for benchmark analysis."""

    def __init__(
        self, aws_region: str = "eu-central-1", results_dir: str = "benchmark_results"
    ):
        """Initialize the metrics collector.

        Args:
            aws_region: AWS region for CloudWatch
            results_dir: Directory to store results
        """
        self.aws_region = aws_region
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # AWS clients
        self.cloudwatch = boto3.client("cloudwatch", region_name=aws_region)
        self.ec2_client = boto3.client("ec2", region_name=aws_region)
        self.logs_client = boto3.client("logs", region_name=aws_region)

        logger.info("CloudWatch Metrics Collector initialized")
        logger.info("AWS Region: %s", aws_region)
        logger.info("Results Directory: %s", self.results_dir)

    def get_ec2_metrics(
        self,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 60,
    ) -> ResourceMetrics:
        """Collect metrics for an EC2 instance.

        Args:
            instance_id: EC2 instance ID
            start_time: Start time for metrics
            end_time: End time for metrics
            period: Period in seconds for metric aggregation

        Returns:
            ResourceMetrics with collected data
        """
        logger.info("Collecting EC2 metrics for instance: %s", instance_id)
        logger.info("Time range: %s to %s", start_time, end_time)

        duration = (end_time - start_time).total_seconds()

        # Define metrics to collect
        ec2_metrics = [
            ("CPUUtilization", "Percent", "AWS/EC2"),
            ("NetworkIn", "Bytes", "AWS/EC2"),
            ("NetworkOut", "Bytes", "AWS/EC2"),
            ("DiskReadBytes", "Bytes", "AWS/EC2"),
            ("DiskWriteBytes", "Bytes", "AWS/EC2"),
            ("DiskReadOps", "Count", "AWS/EC2"),
            ("DiskWriteOps", "Count", "AWS/EC2"),
        ]

        # Custom metrics from CloudWatch agent
        custom_metrics = [
            ("mem_used_percent", "Percent", "CWAgent"),
            ("disk_used_percent", "Percent", "CWAgent"),
            ("cpu_usage_idle", "Percent", "CWAgent"),
            ("cpu_usage_iowait", "Percent", "CWAgent"),
        ]

        metrics = {}

        # Collect standard EC2 metrics
        for metric_name, unit, namespace in ec2_metrics:
            try:
                stats = self._get_metric_statistics(
                    namespace=namespace,
                    metric_name=metric_name,
                    dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    start_time=start_time,
                    end_time=end_time,
                    period=period,
                    unit=unit,
                )
                metrics[metric_name] = stats
                logger.info(
                    "  %s: avg=%.2f, max=%.2f, min=%.2f",
                    metric_name,
                    stats.average or 0,
                    stats.maximum or 0,
                    stats.minimum or 0,
                )
            except Exception as e:
                logger.warning("Failed to collect %s: %s", metric_name, e)

        # Collect custom metrics from CloudWatch agent
        for metric_name, unit, namespace in custom_metrics:
            try:
                stats = self._get_metric_statistics(
                    namespace=namespace,
                    metric_name=metric_name,
                    dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    start_time=start_time,
                    end_time=end_time,
                    period=period,
                    unit=unit,
                )
                metrics[metric_name] = stats
                logger.info(
                    "  %s: avg=%.2f, max=%.2f, min=%.2f",
                    metric_name,
                    stats.average or 0,
                    stats.maximum or 0,
                    stats.minimum or 0,
                )
            except Exception as e:
                logger.debug("Custom metric %s not available: %s", metric_name, e)

        return ResourceMetrics(
            resource_id=instance_id,
            resource_type="ec2",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            metrics=metrics,
        )

    def get_eks_pod_metrics(
        self,
        cluster_name: str,
        namespace: str,
        pod_name_prefix: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 60,
    ) -> ResourceMetrics:
        """Collect metrics for EKS pods.

        Args:
            cluster_name: EKS cluster name
            namespace: Kubernetes namespace
            pod_name_prefix: Prefix for pod names (e.g., 'spark-nyc-taxi')
            start_time: Start time for metrics
            end_time: End time for metrics
            period: Period in seconds for metric aggregation

        Returns:
            ResourceMetrics with collected data
        """
        logger.info("Collecting EKS metrics for cluster: %s", cluster_name)
        logger.info("Namespace: %s, Pod prefix: %s", namespace, pod_name_prefix)
        logger.info("Time range: %s to %s", start_time, end_time)

        duration = (end_time - start_time).total_seconds()

        # Define metrics to collect from Container Insights
        eks_metrics = [
            ("pod_cpu_utilization", "Percent"),
            ("pod_memory_utilization", "Percent"),
            ("pod_network_rx_bytes", "Bytes"),
            ("pod_network_tx_bytes", "Bytes"),
            ("pod_cpu_usage_total", "None"),
            ("pod_memory_working_set", "Bytes"),
        ]

        metrics = {}

        # Collect Container Insights metrics
        for metric_name, unit in eks_metrics:
            try:
                stats = self._get_metric_statistics(
                    namespace="ContainerInsights",
                    metric_name=metric_name,
                    dimensions=[
                        {"Name": "ClusterName", "Value": cluster_name},
                        {"Name": "Namespace", "Value": namespace},
                    ],
                    start_time=start_time,
                    end_time=end_time,
                    period=period,
                    unit=unit,
                )
                metrics[metric_name] = stats
                logger.info(
                    "  %s: avg=%.2f, max=%.2f, min=%.2f",
                    metric_name,
                    stats.average or 0,
                    stats.maximum or 0,
                    stats.minimum or 0,
                )
            except Exception as e:
                logger.warning("Failed to collect %s: %s", metric_name, e)

        resource_id = f"{cluster_name}/{namespace}/{pod_name_prefix}"

        return ResourceMetrics(
            resource_id=resource_id,
            resource_type="eks",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            metrics=metrics,
        )

    def _get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: list[dict[str, str]],
        start_time: datetime,
        end_time: datetime,
        period: int,
        unit: str,
    ) -> MetricStatistics:
        """Get statistics for a CloudWatch metric.

        Args:
            namespace: CloudWatch namespace
            metric_name: Name of the metric
            dimensions: Metric dimensions
            start_time: Start time
            end_time: End time
            period: Period in seconds
            unit: Metric unit

        Returns:
            MetricStatistics with aggregated data
        """
        response = self.cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=["Average", "Maximum", "Minimum", "Sum", "SampleCount"],
            Unit=unit if unit != "None" else None,
        )

        datapoints = response.get("Datapoints", [])

        if not datapoints:
            return MetricStatistics(
                metric_name=metric_name,
                unit=unit,
                sample_count=0,
            )

        # Calculate aggregated statistics
        averages = [dp["Average"] for dp in datapoints if "Average" in dp]
        maximums = [dp["Maximum"] for dp in datapoints if "Maximum" in dp]
        minimums = [dp["Minimum"] for dp in datapoints if "Minimum" in dp]
        sums = [dp["Sum"] for dp in datapoints if "Sum" in dp]

        return MetricStatistics(
            metric_name=metric_name,
            unit=unit,
            average=sum(averages) / len(averages) if averages else None,
            maximum=max(maximums) if maximums else None,
            minimum=min(minimums) if minimums else None,
            sum=sum(sums) if sums else None,
            sample_count=len(datapoints),
            datapoints=sorted(datapoints, key=lambda x: x["Timestamp"]),
        )

    def get_execution_time_from_logs(
        self,
        log_group: str,
        log_stream: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float | None:
        """Extract execution time from CloudWatch logs.

        Args:
            log_group: CloudWatch log group name
            log_stream: Log stream name
            start_time: Start time for log search
            end_time: End time for log search

        Returns:
            Execution time in seconds or None if not found
        """
        try:
            logger.info("Searching logs: %s/%s", log_group, log_stream)

            # Convert to milliseconds
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            # Search for timing information in logs
            response = self.logs_client.filter_log_events(
                logGroupName=log_group,
                logStreamNames=[log_stream],
                startTime=start_ms,
                endTime=end_ms,
                filterPattern=(
                    '"Pipeline completed" OR "Total Time" OR "execution_time"'
                ),
            )

            events = response.get("events", [])

            # Parse execution time from log messages
            for event in events:
                message = event.get("message", "")

                # Look for patterns like "Pipeline completed in 123.45s"
                if "Pipeline completed in" in message:
                    parts = message.split("Pipeline completed in")
                    if len(parts) > 1:
                        time_str = parts[1].strip().split("s")[0]
                        try:
                            return float(time_str)
                        except ValueError:
                            pass

                # Look for patterns like "Total Time: 123.45s"
                if "Total Time:" in message:
                    parts = message.split("Total Time:")
                    if len(parts) > 1:
                        time_str = parts[1].strip().split("s")[0]
                        try:
                            return float(time_str)
                        except ValueError:
                            pass

            logger.warning("Could not find execution time in logs")

        except Exception as e:
            logger.error("Error reading logs: %s", e)
        else:
            return None

    def save_metrics(
        self, metrics: ResourceMetrics, output_file: str | None = None
    ) -> str:
        """Save metrics to a JSON file.

        Args:
            metrics: ResourceMetrics to save
            output_file: Optional output file path

        Returns:
            Path to saved file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = str(
                self.results_dir
                / f"cloudwatch_metrics_{metrics.resource_type}_{timestamp}.json"
            )

        # Convert to serializable format
        data = {
            "resource_id": metrics.resource_id,
            "resource_type": metrics.resource_type,
            "start_time": metrics.start_time.isoformat(),
            "end_time": metrics.end_time.isoformat(),
            "duration_seconds": metrics.duration_seconds,
            "metrics": {
                name: {
                    "metric_name": stat.metric_name,
                    "unit": stat.unit,
                    "average": stat.average,
                    "maximum": stat.maximum,
                    "minimum": stat.minimum,
                    "sum": stat.sum,
                    "sample_count": stat.sample_count,
                    "datapoints": [
                        {
                            "timestamp": dp["Timestamp"].isoformat(),
                            "average": dp.get("Average"),
                            "maximum": dp.get("Maximum"),
                            "minimum": dp.get("Minimum"),
                            "sum": dp.get("Sum"),
                        }
                        for dp in (stat.datapoints or [])
                    ],
                }
                for name, stat in metrics.metrics.items()
            },
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Metrics saved to: %s", output_file)
        return output_file


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Collect CloudWatch metrics for benchmark analysis"
    )
    parser.add_argument(
        "--ec2-instance",
        type=str,
        help="EC2 instance ID to collect metrics for",
    )
    parser.add_argument(
        "--eks-cluster",
        type=str,
        help="EKS cluster name to collect metrics for",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="default",
        help="Kubernetes namespace (default: default)",
    )
    parser.add_argument(
        "--pod-prefix",
        type=str,
        default="spark-nyc-taxi",
        help="Pod name prefix (default: spark-nyc-taxi)",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        help="Start time (ISO format or relative like '1h', '30m')",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        help="End time (ISO format, default: now)",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=60,
        help="Metric period in seconds (default: 60)",
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
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: auto-generated)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.ec2_instance and not args.eks_cluster:
        logger.error("Must specify either --ec2-instance or --eks-cluster")
        sys.exit(1)

    # Parse time range
    if args.end_time:
        end_time = datetime.fromisoformat(args.end_time)
    else:
        end_time = datetime.now()

    if args.start_time:
        if args.start_time.endswith("h"):
            hours = int(args.start_time[:-1])
            start_time = end_time - timedelta(hours=hours)
        elif args.start_time.endswith("m"):
            minutes = int(args.start_time[:-1])
            start_time = end_time - timedelta(minutes=minutes)
        else:
            start_time = datetime.fromisoformat(args.start_time)
    else:
        # Default to last hour
        start_time = end_time - timedelta(hours=1)

    # Create collector
    collector = CloudWatchMetricsCollector(
        aws_region=args.region,
        results_dir=args.results_dir,
    )

    try:
        # Collect metrics
        if args.ec2_instance:
            metrics = collector.get_ec2_metrics(
                instance_id=args.ec2_instance,
                start_time=start_time,
                end_time=end_time,
                period=args.period,
            )
        else:
            metrics = collector.get_eks_pod_metrics(
                cluster_name=args.eks_cluster,
                namespace=args.namespace,
                pod_name_prefix=args.pod_prefix,
                start_time=start_time,
                end_time=end_time,
                period=args.period,
            )

        # Save metrics
        output_file = collector.save_metrics(metrics, args.output)

        logger.info("\nMetrics collection complete!")
        logger.info("Output file: %s", output_file)

    except Exception as e:
        logger.error("Failed to collect metrics: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
