#!/usr/bin/env python3
"""Run orchestrated TPC-H benchmark with concurrent jobs.

This script demonstrates the multi-job orchestration capability by:
1. Submitting multiple Spark jobs to EKS
2. Submitting multiple Polars jobs to AWS Batch
3. Monitoring all jobs and recording timestamps
4. Calculating startup latency
5. Collecting metrics from S3
6. Saving aggregated results

Usage:
    python scripts/run_orchestrated_benchmark.py --spark-jobs 10 --batch-jobs 10 --scale-factor 10
"""

import argparse
import sys
from pathlib import Path

# Add src to path BEFORE importing from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration import JobOrchestrator
from src.utils.logging_config import get_logger

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run orchestrated TPC-H benchmark with concurrent jobs"
    )

    parser.add_argument(
        "--spark-jobs",
        type=int,
        default=10,
        help="Number of Spark jobs to submit (default: 10)",
    )

    parser.add_argument(
        "--batch-jobs",
        type=int,
        default=10,
        help="Number of Batch jobs to submit (default: 10)",
    )

    parser.add_argument(
        "--scale-factor",
        type=int,
        default=10,
        choices=[1, 10, 100],
        help="TPC-H scale factor (default: 10)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Job status poll interval in seconds (default: 5)",
    )

    parser.add_argument(
        "--max-wait-time",
        type=int,
        default=3600,
        help="Maximum wait time for all jobs in seconds (default: 3600)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="orchestration_metrics.json",
        help="Output file for aggregated metrics (default: orchestration_metrics.json)",
    )

    parser.add_argument(
        "--skip-spark",
        action="store_true",
        help="Skip Spark job submission (Batch only)",
    )

    parser.add_argument(
        "--skip-batch",
        action="store_true",
        help="Skip Batch job submission (Spark only)",
    )

    return parser.parse_args()


def main() -> int:
    """Main orchestration workflow."""
    args = parse_args()

    logger.info("=" * 80)
    logger.info("TPC-H Orchestrated Benchmark")
    logger.info("=" * 80)
    logger.info("Configuration:")
    logger.info(f"  Spark jobs: {args.spark_jobs if not args.skip_spark else 0}")
    logger.info(f"  Batch jobs: {args.batch_jobs if not args.skip_batch else 0}")
    logger.info(f"  Scale factor: {args.scale_factor}")
    logger.info(f"  Poll interval: {args.poll_interval}s")
    logger.info(f"  Max wait time: {args.max_wait_time}s")
    logger.info(f"  Output file: {args.output}")
    logger.info("=" * 80)

    try:
        # Initialize orchestrator
        logger.info("Initializing JobOrchestrator...")
        orchestrator = JobOrchestrator()

        # Submit jobs
        all_submissions = []

        if not args.skip_spark:
            logger.info(f"\nSubmitting {args.spark_jobs} Spark jobs to EKS...")
            spark_submissions = orchestrator.submit_spark_jobs(
                count=args.spark_jobs,
                scale_factor=args.scale_factor,
            )
            all_submissions.extend(spark_submissions)
            logger.info(f"✓ Submitted {len(spark_submissions)} Spark jobs")

        if not args.skip_batch:
            logger.info(f"\nSubmitting {args.batch_jobs} Batch jobs to AWS Batch...")
            # Get matching resources for fair comparison
            resources = orchestrator._get_resource_config(args.scale_factor)
            batch_submissions = orchestrator.submit_batch_jobs(
                count=args.batch_jobs,
                scale_factor=args.scale_factor,
                vcpu=resources["batch_vcpu"],
                memory_gb=resources["batch_memory_gb"],
            )
            all_submissions.extend(batch_submissions)
            logger.info(f"✓ Submitted {len(batch_submissions)} Batch jobs")

        if not all_submissions:
            logger.error(
                "No jobs submitted! Use --skip-spark or --skip-batch, not both."
            )
            return 1

        logger.info(f"\n{'=' * 80}")
        logger.info(f"Total jobs submitted: {len(all_submissions)}")
        logger.info(f"{'=' * 80}")

        # Monitor jobs
        logger.info("\nMonitoring job execution...")
        metrics = orchestrator.monitor_jobs(
            all_submissions,
            poll_interval=args.poll_interval,
            max_wait_time=args.max_wait_time,
        )
        logger.info(f"✓ All {len(metrics)} jobs completed")

        # Calculate startup latency
        logger.info("\nCalculating startup latency...")
        metrics = orchestrator.calculate_startup_latency(metrics)
        logger.info("✓ Startup latency calculated")

        # Collect metrics from S3
        logger.info("\nCollecting execution metrics from S3...")
        metrics = orchestrator.collect_metrics_from_s3(metrics)
        logger.info("✓ Metrics collected from S3")

        # Save aggregated metrics
        logger.info(f"\nSaving aggregated metrics to {args.output}...")
        orchestrator.save_aggregated_metrics(metrics, args.output)
        logger.info(f"✓ Metrics saved to {args.output}")

        # Print summary
        logger.info(f"\n{'=' * 80}")
        logger.info("Benchmark Summary")
        logger.info(f"{'=' * 80}")

        succeeded = sum(1 for m in metrics if m.status == "SUCCEEDED")
        failed = sum(1 for m in metrics if m.status == "FAILED")

        logger.info(f"Total jobs: {len(metrics)}")
        logger.info(f"  Succeeded: {succeeded}")
        logger.info(f"  Failed: {failed}")

        # Startup latency summary
        spark_metrics = [m for m in metrics if m.job_type == "spark"]
        batch_metrics = [m for m in metrics if m.job_type == "polars"]

        if spark_metrics:
            spark_latencies = [
                m.startup_latency_seconds
                for m in spark_metrics
                if m.startup_latency_seconds is not None
            ]
            if spark_latencies:
                avg_spark = sum(spark_latencies) / len(spark_latencies)
                logger.info(f"\nSpark (EKS) startup latency: {avg_spark:.2f}s average")

        if batch_metrics:
            batch_latencies = [
                m.startup_latency_seconds
                for m in batch_metrics
                if m.startup_latency_seconds is not None
            ]
            if batch_latencies:
                avg_batch = sum(batch_latencies) / len(batch_latencies)
                logger.info(f"Polars (Batch) startup latency: {avg_batch:.2f}s average")

        logger.info(f"\n{'=' * 80}")
        logger.info("Orchestration complete!")
        logger.info(f"{'=' * 80}")

    except KeyboardInterrupt:
        logger.warning("\nBenchmark interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"\nBenchmark failed: {e}", exc_info=True)
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
