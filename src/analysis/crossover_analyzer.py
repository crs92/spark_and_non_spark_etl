"""Crossover point analysis module.

This module analyzes benchmark results to identify the crossover point
where distributed processing (Spark on EKS) becomes more cost-effective
than single-node processing (Polars on EC2).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.analysis.cost_calculator import (
    CostCalculator,
    InstanceType,
)
from src.analysis.tco_analyzer import TCOAnalyzer
from src.etl.nyc_taxi_config import DATASETS, DataSize


@dataclass
class BenchmarkResult:
    """Benchmark result for a single data size."""

    data_size: str
    data_size_gb: float
    polars_time_seconds: float
    spark_time_seconds: float
    polars_memory_mb: float
    spark_memory_mb: float


@dataclass
class CrossoverPoint:
    """Crossover point analysis result."""

    # Performance crossover
    performance_crossover_size: str | None
    performance_crossover_gb: float | None
    performance_crossover_message: str

    # Cost crossover
    cost_crossover_size: str | None
    cost_crossover_gb: float | None
    cost_crossover_message: str

    # TCO crossover
    tco_crossover_size: str | None
    tco_crossover_gb: float | None
    tco_crossover_message: str

    # Supporting data
    analysis_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert crossover point to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "performance_crossover": {
                "size": self.performance_crossover_size,
                "size_gb": self.performance_crossover_gb,
                "message": self.performance_crossover_message,
            },
            "cost_crossover": {
                "size": self.cost_crossover_size,
                "size_gb": self.cost_crossover_gb,
                "message": self.cost_crossover_message,
            },
            "tco_crossover": {
                "size": self.tco_crossover_size,
                "size_gb": self.tco_crossover_gb,
                "message": self.tco_crossover_message,
            },
            "analysis_data": self.analysis_data,
        }


class CrossoverAnalyzer:
    """Analyzer for identifying crossover points in benchmark results."""

    def __init__(
        self,
        ec2_instance_type: InstanceType = InstanceType.R6I_2XLARGE,
        eks_node_instance_type: InstanceType = InstanceType.R6I_2XLARGE,
        eks_num_nodes: int = 3,
        region: str = "us-east-1",
    ):
        """Initialize crossover analyzer.

        Args:
            ec2_instance_type: EC2 instance type for Polars
            eks_node_instance_type: EKS node instance type for Spark
            eks_num_nodes: Number of EKS nodes
            region: AWS region for pricing (default: us-east-1)
        """
        self.ec2_instance_type = ec2_instance_type
        self.eks_node_instance_type = eks_node_instance_type
        self.eks_num_nodes = eks_num_nodes
        self.region = region
        self.cost_calculator = CostCalculator()

    def load_benchmark_results(self, results_dir: Path | str) -> list[BenchmarkResult]:
        """Load benchmark results from JSON files.

        Args:
            results_dir: Directory containing benchmark result JSON files

        Returns:
            List of benchmark results
        """
        results_dir = Path(results_dir)
        benchmark_results = []

        # Load all benchmark JSON files
        for json_file in sorted(results_dir.glob("benchmark_full_*.json")):
            with open(json_file) as f:
                data = json.load(f)

            # Extract data size from metadata
            data_size = data["metadata"]["data_size"]
            dataset = DATASETS.get(DataSize(data_size))

            if not dataset:
                continue

            # Extract timing data
            polars_time = data["polars"]["total_time"]
            spark_time = data["spark"]["total_time"]

            # Extract memory data
            polars_memory = data["polars"]["bulk"]["timing_metrics"]["resources"][
                "peak_memory_mb"
            ]
            spark_memory = data["spark"]["bulk"]["timing_metrics"]["resources"][
                "peak_memory_mb"
            ]

            benchmark_results.append(
                BenchmarkResult(
                    data_size=data_size,
                    data_size_gb=dataset.approx_size_gb,
                    polars_time_seconds=polars_time,
                    spark_time_seconds=spark_time,
                    polars_memory_mb=polars_memory,
                    spark_memory_mb=spark_memory,
                )
            )

        return benchmark_results

    def analyze_performance_crossover(
        self, results: list[BenchmarkResult]
    ) -> dict[str, Any]:
        """Analyze where Spark becomes faster than Polars.

        Args:
            results: List of benchmark results

        Returns:
            Performance crossover analysis
        """
        crossover_found = False
        crossover_size = None
        crossover_gb = None

        performance_data = []

        for result in results:
            speedup = result.polars_time_seconds / result.spark_time_seconds
            winner = "Polars" if speedup > 1 else "Spark"

            performance_data.append({
                "data_size": result.data_size,
                "data_size_gb": result.data_size_gb,
                "polars_time": result.polars_time_seconds,
                "spark_time": result.spark_time_seconds,
                "speedup": speedup,
                "winner": winner,
            })

            # Check if this is the crossover point
            if not crossover_found and winner == "Spark":
                crossover_found = True
                crossover_size = result.data_size
                crossover_gb = result.data_size_gb

        if crossover_found:
            message = f"Spark becomes faster at {crossover_size} ({crossover_gb}GB)"
        else:
            message = "Polars is faster across all tested data sizes"

        return {
            "crossover_found": crossover_found,
            "crossover_size": crossover_size,
            "crossover_gb": crossover_gb,
            "message": message,
            "performance_data": performance_data,
        }

    def analyze_cost_crossover(self, results: list[BenchmarkResult]) -> dict[str, Any]:
        """Analyze where Spark becomes more cost-effective than Polars.

        Args:
            results: List of benchmark results

        Returns:
            Cost crossover analysis
        """
        crossover_found = False
        crossover_size = None
        crossover_gb = None

        cost_data = []

        for result in results:
            # Calculate EC2 cost
            ec2_model = self.cost_calculator.calculate_ec2_cost(
                instance_type=self.ec2_instance_type,
                execution_time_seconds=result.polars_time_seconds,
                data_size_gb=result.data_size_gb,
                region=self.region,
            )

            # Calculate EKS cost
            eks_model = self.cost_calculator.calculate_eks_cost(
                node_instance_type=self.eks_node_instance_type,
                num_nodes=self.eks_num_nodes,
                execution_time_seconds=result.spark_time_seconds,
                data_size_gb=result.data_size_gb,
                region=self.region,
            )

            ec2_cost = ec2_model.calculate_total_cost()
            eks_cost = eks_model.calculate_total_cost()

            winner = "EC2" if ec2_cost < eks_cost else "EKS"
            cost_ratio = eks_cost / ec2_cost if ec2_cost > 0 else 0

            cost_data.append({
                "data_size": result.data_size,
                "data_size_gb": result.data_size_gb,
                "ec2_cost": ec2_cost,
                "eks_cost": eks_cost,
                "cost_ratio": cost_ratio,
                "winner": winner,
                "ec2_cost_per_gb": ec2_model.calculate_cost_per_gb(),
                "eks_cost_per_gb": eks_model.calculate_cost_per_gb(),
            })

            # Check if this is the crossover point
            if not crossover_found and winner == "EKS":
                crossover_found = True
                crossover_size = result.data_size
                crossover_gb = result.data_size_gb

        if crossover_found:
            message = (
                "EKS becomes more cost-effective at"
                f" {crossover_size} ({crossover_gb}GB)"
            )
        else:
            message = "EC2 is more cost-effective across all tested data sizes"

        return {
            "crossover_found": crossover_found,
            "crossover_size": crossover_size,
            "crossover_gb": crossover_gb,
            "message": message,
            "cost_data": cost_data,
        }

    def analyze_tco_crossover(self, results: list[BenchmarkResult]) -> dict[str, Any]:
        """Analyze where Spark becomes more cost-effective including TCO.

        Args:
            results: List of benchmark results

        Returns:
            TCO crossover analysis
        """
        crossover_found = False
        crossover_size = None
        crossover_gb = None

        tco_data = []

        for result in results:
            # Calculate EC2 cost model
            ec2_cost_model = self.cost_calculator.calculate_ec2_cost(
                instance_type=self.ec2_instance_type,
                execution_time_seconds=result.polars_time_seconds,
                data_size_gb=result.data_size_gb,
                region=self.region,
            )

            # Calculate EKS cost model
            eks_cost_model = self.cost_calculator.calculate_eks_cost(
                node_instance_type=self.eks_node_instance_type,
                num_nodes=self.eks_num_nodes,
                execution_time_seconds=result.spark_time_seconds,
                data_size_gb=result.data_size_gb,
                region=self.region,
            )

            # Create TCO reports
            ec2_tco = TCOAnalyzer.create_ec2_tco_report(ec2_cost_model)
            eks_tco = TCOAnalyzer.create_eks_tco_report(eks_cost_model)

            ec2_first_year = ec2_tco.calculate_first_year_tco()
            eks_first_year = eks_tco.calculate_first_year_tco()

            winner = "EC2" if ec2_first_year < eks_first_year else "EKS"
            tco_ratio = eks_first_year / ec2_first_year if ec2_first_year > 0 else 0

            tco_data.append({
                "data_size": result.data_size,
                "data_size_gb": result.data_size_gb,
                "ec2_first_year_tco": ec2_first_year,
                "eks_first_year_tco": eks_first_year,
                "tco_ratio": tco_ratio,
                "winner": winner,
                "ec2_complexity": ec2_tco.operational_overhead.get_complexity_score(),
                "eks_complexity": eks_tco.operational_overhead.get_complexity_score(),
            })

            # Check if this is the crossover point
            if not crossover_found and winner == "EKS":
                crossover_found = True
                crossover_size = result.data_size
                crossover_gb = result.data_size_gb

        if crossover_found:
            message = (
                "EKS becomes more cost-effective (TCO) at"
                f" {crossover_size} ({crossover_gb}GB)"
            )
        else:
            message = "EC2 is more cost-effective (TCO) across all tested data sizes"

        return {
            "crossover_found": crossover_found,
            "crossover_size": crossover_size,
            "crossover_gb": crossover_gb,
            "message": message,
            "tco_data": tco_data,
        }

    def analyze_crossover_point(self, results: list[BenchmarkResult]) -> CrossoverPoint:
        """Perform comprehensive crossover point analysis.

        Args:
            results: List of benchmark results

        Returns:
            Crossover point analysis
        """
        # Analyze performance crossover
        performance_analysis = self.analyze_performance_crossover(results)

        # Analyze cost crossover
        cost_analysis = self.analyze_cost_crossover(results)

        # Analyze TCO crossover
        tco_analysis = self.analyze_tco_crossover(results)

        return CrossoverPoint(
            performance_crossover_size=performance_analysis["crossover_size"],
            performance_crossover_gb=performance_analysis["crossover_gb"],
            performance_crossover_message=performance_analysis["message"],
            cost_crossover_size=cost_analysis["crossover_size"],
            cost_crossover_gb=cost_analysis["crossover_gb"],
            cost_crossover_message=cost_analysis["message"],
            tco_crossover_size=tco_analysis["crossover_size"],
            tco_crossover_gb=tco_analysis["crossover_gb"],
            tco_crossover_message=tco_analysis["message"],
            analysis_data={
                "performance": performance_analysis,
                "cost": cost_analysis,
                "tco": tco_analysis,
            },
        )

    def generate_decision_framework(self, crossover: CrossoverPoint) -> dict[str, Any]:
        """Generate decision framework based on crossover analysis.

        Args:
            crossover: Crossover point analysis

        Returns:
            Decision framework with recommendations
        """
        recommendations = []

        # Performance-based recommendation
        if crossover.performance_crossover_gb:
            recommendations.append({
                "criterion": "Performance",
                "use_polars_when": (
                    f"Data size < {crossover.performance_crossover_gb}GB"
                ),
                "use_spark_when": (
                    f"Data size >= {crossover.performance_crossover_gb}GB"
                ),
                "reason": "Spark becomes faster at this scale",
            })
        else:
            recommendations.append({
                "criterion": "Performance",
                "use_polars_when": "All tested data sizes",
                "use_spark_when": "Never (based on current tests)",
                "reason": "Polars is faster across all tested scales",
            })

        # Cost-based recommendation
        if crossover.cost_crossover_gb:
            recommendations.append({
                "criterion": "Infrastructure Cost",
                "use_polars_when": f"Data size < {crossover.cost_crossover_gb}GB",
                "use_spark_when": f"Data size >= {crossover.cost_crossover_gb}GB",
                "reason": "EKS becomes more cost-effective at this scale",
            })
        else:
            recommendations.append({
                "criterion": "Infrastructure Cost",
                "use_polars_when": "All tested data sizes",
                "use_spark_when": "Never (based on current tests)",
                "reason": "EC2 is cheaper across all tested scales",
            })

        # TCO-based recommendation
        if crossover.tco_crossover_gb:
            recommendations.append({
                "criterion": "Total Cost of Ownership",
                "use_polars_when": f"Data size < {crossover.tco_crossover_gb}GB",
                "use_spark_when": f"Data size >= {crossover.tco_crossover_gb}GB",
                "reason": "EKS TCO becomes favorable at this scale",
            })
        else:
            recommendations.append({
                "criterion": "Total Cost of Ownership",
                "use_polars_when": "All tested data sizes",
                "use_spark_when": "Never (based on current tests)",
                "reason": "EC2 has lower TCO across all tested scales",
            })

        # General recommendations
        general_recommendations = [
            {
                "scenario": "Small to medium datasets (< 10GB)",
                "recommendation": "Use Polars on EC2",
                "reasons": [
                    "Faster execution time",
                    "Lower infrastructure cost",
                    "Simpler deployment and debugging",
                    "Lower operational overhead",
                ],
            },
            {
                "scenario": "Large datasets (> 50GB)",
                "recommendation": "Consider Spark on EKS",
                "reasons": [
                    "Better scalability",
                    "Fault tolerance",
                    "Distributed processing capabilities",
                    "May become cost-effective at scale",
                ],
            },
            {
                "scenario": "Operational simplicity is priority",
                "recommendation": "Use Polars on EC2",
                "reasons": [
                    "2 hours deployment vs 8 hours for EKS",
                    "Simple SSH debugging vs K8s complexity",
                    "2 hours/month maintenance vs 8 hours/month",
                ],
            },
            {
                "scenario": "Need for horizontal scaling",
                "recommendation": "Use Spark on EKS",
                "reasons": [
                    "Dynamic resource allocation",
                    "Multiple concurrent jobs",
                    "Integration with existing K8s infrastructure",
                ],
            },
        ]

        return {
            "crossover_recommendations": recommendations,
            "general_recommendations": general_recommendations,
            "summary": self._generate_summary(crossover),
        }

    def _generate_summary(self, crossover: CrossoverPoint) -> str:
        """Generate summary text for decision framework.

        Args:
            crossover: Crossover point analysis

        Returns:
            Summary text
        """
        summary_parts = []

        summary_parts.append("# Vertical vs. Horizontal Scaling Decision Framework\n")

        summary_parts.append("## Key Findings\n")
        summary_parts.append(f"- {crossover.performance_crossover_message}")
        summary_parts.append(f"- {crossover.cost_crossover_message}")
        summary_parts.append(f"- {crossover.tco_crossover_message}")

        summary_parts.append("\n## The Bottom Line\n")
        summary_parts.append(
            "For most small to medium ETL workloads, Polars on EC2 provides:"
        )
        summary_parts.append("- Faster execution times")
        summary_parts.append("- Lower costs")
        summary_parts.append("- Simpler operations")
        summary_parts.append(
            "\nSpark on EKS becomes valuable when you need horizontal scaling, "
            "fault tolerance, or are processing very large datasets."
        )

        return "\n".join(summary_parts)
