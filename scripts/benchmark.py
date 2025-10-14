#!/usr/bin/env python3
"""ETL Performance Benchmarking Script Measures setup time, execution time, and
resource usage for both ETL approaches."""

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class BenchmarkResult:
    """Benchmark result data structure."""

    stack_type: str
    image_pull_time: float
    container_start_time: float
    execution_time: float
    total_time: float
    peak_memory_mb: float
    avg_cpu_percent: float
    exit_code: int
    timestamp: str


class ETLBenchmark:
    """ETL benchmarking class for comparing Spark vs Pythonic approaches."""

    def __init__(self, data_size: str = "small"):
        self.data_size = data_size
        self.results: dict[str, BenchmarkResult] = {}
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(
                    f'benchmark_{self.data_size}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
                ),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def measure_image_pull_time(self, image_name: str) -> float:
        """Measure time to pull Docker image."""
        self.logger.info(f"Measuring image pull time for {image_name}")

        # Remove image if exists to ensure fresh pull
        subprocess.run(["docker", "rmi", image_name], capture_output=True, check=False)

        start_time = time.time()
        result = subprocess.run(
            ["docker", "pull", image_name],
            capture_output=True,
            text=True,
            check=False,
        )
        pull_time = time.time() - start_time

        if result.returncode != 0:
            self.logger.error(f"Failed to pull image {image_name}: {result.stderr}")
            return 0.0

        self.logger.info(f"Image pull time for {image_name}: {pull_time:.2f}s")
        return pull_time

    def measure_container_startup(self, service_name: str, profile: str) -> float:
        """Measure container startup time."""
        self.logger.info(f"Measuring container startup time for {service_name}")

        start_time = time.time()
        result = subprocess.run(
            [
                "docker-compose",
                "--profile",
                profile,
                "up",
                "-d",
                service_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self.logger.error(f"Failed to start {service_name}: {result.stderr}")
            return 0.0

        # Wait for container to be ready
        container_name = (
            f"{service_name}-service"
            if service_name != "dev-env"
            else "etl-development"
        )

        while True:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    container_name,
                    "--format={{.State.Running}}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip() == "true":
                break
            time.sleep(0.1)

        startup_time = time.time() - start_time
        self.logger.info(
            f"Container startup time for {service_name}: {startup_time:.2f}s",
        )
        return startup_time

    def monitor_execution(self, container_name: str, command: list) -> dict[str, Any]:
        """Monitor execution time and resource usage."""
        self.logger.info(f"Starting execution monitoring for {container_name}")

        # Start resource monitoring
        start_time = time.time()
        peak_memory = 0
        cpu_samples = []

        # Execute the ETL command
        process = subprocess.Popen(
            [
                "docker",
                "exec",
                container_name,
            ]
            + command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Monitor resources while process runs
        while process.poll() is None:
            try:
                # Get container stats
                stats_result = subprocess.run(
                    [
                        "docker",
                        "stats",
                        container_name,
                        "--no-stream",
                        "--format",
                        "table {{.MemUsage}}\t{{.CPUPerc}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if stats_result.returncode == 0:
                    lines = stats_result.stdout.strip().split("\n")
                    if len(lines) > 1:  # Skip header
                        stats_line = lines[1]
                        parts = stats_line.split("\t")
                        if len(parts) >= 2:
                            # Parse memory usage (format: "123.4MiB / 2GiB")
                            mem_part = parts[0].split(" / ")[0]
                            if "MiB" in mem_part:
                                memory_mb = float(mem_part.replace("MiB", ""))
                            elif "GiB" in mem_part:
                                memory_mb = float(mem_part.replace("GiB", "")) * 1024
                            else:
                                memory_mb = 0

                            peak_memory = max(peak_memory, memory_mb)

                            # Parse CPU usage
                            cpu_str = parts[1].replace("%", "")
                            if cpu_str != "--":
                                cpu_samples.append(float(cpu_str))

            except (ValueError, IndexError):
                pass

            time.sleep(0.5)

        execution_time = time.time() - start_time
        stdout, stderr = process.communicate()

        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0

        self.logger.info(f"Execution completed in {execution_time:.2f}s")
        self.logger.info(f"Peak memory: {peak_memory:.2f} MB")
        self.logger.info(f"Average CPU: {avg_cpu:.2f}%")

        return {
            "execution_time": execution_time,
            "peak_memory_mb": peak_memory,
            "avg_cpu_percent": avg_cpu,
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    def benchmark_stack(
        self,
        stack_type: str,
        profile: str,
        service_name: str,
        image_name: str,
        command: list,
    ) -> BenchmarkResult:
        """Benchmark a complete ETL stack."""
        self.logger.info(f"Starting benchmark for {stack_type} stack")

        # Ensure clean state
        subprocess.run(
            ["docker-compose", "down", "-v"],
            capture_output=True,
            check=False,
        )

        # Start infrastructure services
        subprocess.run(
            [
                "docker-compose",
                "up",
                "-d",
                "minio",
                "postgres",
            ],
            capture_output=True,
            check=False,
        )

        # Wait for infrastructure to be ready
        time.sleep(10)

        # Measure image pull time
        pull_time = self.measure_image_pull_time(image_name)

        # Measure container startup
        startup_time = self.measure_container_startup(service_name, profile)

        # Monitor execution
        container_name = (
            f"{service_name}-service"
            if service_name != "dev-env"
            else "etl-development"
        )
        execution_metrics = self.monitor_execution(container_name, command)

        # Calculate total time
        total_time = pull_time + startup_time + execution_metrics["execution_time"]

        # Create result
        result = BenchmarkResult(
            stack_type=stack_type,
            image_pull_time=pull_time,
            container_start_time=startup_time,
            execution_time=execution_metrics["execution_time"],
            total_time=total_time,
            peak_memory_mb=execution_metrics["peak_memory_mb"],
            avg_cpu_percent=execution_metrics["avg_cpu_percent"],
            exit_code=execution_metrics["exit_code"],
            timestamp=datetime.now().isoformat(),
        )

        self.logger.info(f"Benchmark completed for {stack_type}")
        self.logger.info(f"Total time: {total_time:.2f}s")

        return result

    def run_comparison(self) -> dict[str, BenchmarkResult]:
        """Run comparison between both ETL approaches."""
        self.logger.info("Starting ETL comparison benchmark")

        # Benchmark configurations
        benchmarks = [
            {
                "stack_type": "pythonic",
                "profile": "pythonic",
                "service_name": "pythonic-etl",
                "image_name": "spark_and_non_spark_etl-pythonic-etl",
                "command": ["python", "-m", "src.etl.non_spark_etl"],
            },
            {
                "stack_type": "spark",
                "profile": "spark",
                "service_name": "spark-etl",
                "image_name": "spark_and_non_spark_etl-spark-etl",
                "command": ["python", "-m", "src.etl.spark_etl"],
            },
        ]

        results = {}

        for config in benchmarks:
            try:
                result = self.benchmark_stack(**config)
                results[config["stack_type"]] = result
                self.results[config["stack_type"]] = result

                # Clean up between benchmarks
                subprocess.run(
                    ["docker-compose", "down"],
                    capture_output=True,
                    check=False,
                )
                time.sleep(5)

            except Exception as e:
                self.logger.error(f"Failed to benchmark {config['stack_type']}: {e}")

        return results

    def save_results(self, filename: str = None):
        """Save benchmark results to JSON file."""
        if filename is None:
            filename = f"benchmark_results_{self.data_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        results_dict = {}
        for stack_type, result in self.results.items():
            results_dict[stack_type] = {
                "stack_type": result.stack_type,
                "image_pull_time": result.image_pull_time,
                "container_start_time": result.container_start_time,
                "execution_time": result.execution_time,
                "total_time": result.total_time,
                "peak_memory_mb": result.peak_memory_mb,
                "avg_cpu_percent": result.avg_cpu_percent,
                "exit_code": result.exit_code,
                "timestamp": result.timestamp,
            }

        with open(filename, "w") as f:
            json.dump(results_dict, f, indent=2)

        self.logger.info(f"Results saved to {filename}")

    def print_comparison(self):
        """Print comparison results."""
        if len(self.results) < 2:
            self.logger.warning("Need at least 2 results for comparison")
            return

        pythonic = self.results.get("pythonic")
        spark = self.results.get("spark")

        if not pythonic or not spark:
            self.logger.warning("Missing results for comparison")
            return

        print("\n" + "=" * 60)
        print("ETL STACK COMPARISON RESULTS")
        print("=" * 60)

        print(f"{'Metric':<25} {'Pythonic':<15} {'Spark':<15} {'Winner':<10}")
        print("-" * 65)

        metrics = [
            ("Image Pull Time (s)", "image_pull_time"),
            ("Container Start (s)", "container_start_time"),
            ("Execution Time (s)", "execution_time"),
            ("Total Time (s)", "total_time"),
            ("Peak Memory (MB)", "peak_memory_mb"),
            ("Avg CPU (%)", "avg_cpu_percent"),
        ]

        for metric_name, attr in metrics:
            p_val = getattr(pythonic, attr)
            s_val = getattr(spark, attr)

            if attr in [
                "total_time",
                "execution_time",
                "image_pull_time",
                "container_start_time",
            ]:
                winner = "Pythonic" if p_val < s_val else "Spark"
            else:  # For memory and CPU, lower is generally better
                winner = "Pythonic" if p_val < s_val else "Spark"

            print(f"{metric_name:<25} {p_val:<15.2f} {s_val:<15.2f} {winner:<10}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ETL Performance Benchmark")
    parser.add_argument(
        "--data-size",
        choices=["small", "medium", "large"],
        default="small",
        help="Size of test dataset",
    )
    args = parser.parse_args()

    benchmark = ETLBenchmark(args.data_size)
    results = benchmark.run_comparison()
    benchmark.save_results()
    benchmark.print_comparison()
