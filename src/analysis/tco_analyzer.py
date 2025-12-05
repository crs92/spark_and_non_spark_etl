"""Total Cost of Ownership (TCO) analysis module.

This module provides TCO analysis including operational overhead costs
such as deployment time, monitoring setup, and debugging complexity.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.analysis.cost_calculator import EC2CostModel, EKSCostModel


class ComplexityLevel(Enum):
    """Complexity levels for operational tasks."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


@dataclass
class OperationalOverhead:
    """Operational overhead costs for a deployment approach."""

    # Time costs (in hours)
    deployment_time_hours: float
    monitoring_setup_hours: float
    debugging_complexity_hours: float
    maintenance_hours_per_month: float

    # Complexity ratings
    deployment_complexity: ComplexityLevel
    monitoring_complexity: ComplexityLevel
    debugging_complexity: ComplexityLevel

    # Cost per hour for engineering time (default: $100/hr)
    engineer_hourly_rate: float = 100.0

    def calculate_initial_setup_cost(self) -> float:
        """Calculate one-time initial setup cost.

        Returns:
            Initial setup cost in USD
        """
        total_hours = (
            self.deployment_time_hours
            + self.monitoring_setup_hours
            + self.debugging_complexity_hours
        )
        return total_hours * self.engineer_hourly_rate

    def calculate_monthly_maintenance_cost(self) -> float:
        """Calculate ongoing monthly maintenance cost.

        Returns:
            Monthly maintenance cost in USD
        """
        return self.maintenance_hours_per_month * self.engineer_hourly_rate

    def calculate_annual_maintenance_cost(self) -> float:
        """Calculate annual maintenance cost.

        Returns:
            Annual maintenance cost in USD
        """
        return self.calculate_monthly_maintenance_cost() * 12

    def get_complexity_score(self) -> float:
        """Calculate overall complexity score (1-4 scale).

        Returns:
            Average complexity score
        """
        scores = [
            self.deployment_complexity.value,
            self.monitoring_complexity.value,
            self.debugging_complexity.value,
        ]
        return sum(scores) / len(scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert operational overhead to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "deployment_time_hours": self.deployment_time_hours,
            "monitoring_setup_hours": self.monitoring_setup_hours,
            "debugging_complexity_hours": self.debugging_complexity_hours,
            "maintenance_hours_per_month": self.maintenance_hours_per_month,
            "deployment_complexity": self.deployment_complexity.name,
            "monitoring_complexity": self.monitoring_complexity.name,
            "debugging_complexity": self.debugging_complexity.name,
            "engineer_hourly_rate": self.engineer_hourly_rate,
            "initial_setup_cost": self.calculate_initial_setup_cost(),
            "monthly_maintenance_cost": self.calculate_monthly_maintenance_cost(),
            "annual_maintenance_cost": self.calculate_annual_maintenance_cost(),
            "complexity_score": self.get_complexity_score(),
        }


@dataclass
class TCOReport:
    """Total Cost of Ownership report."""

    # Infrastructure costs
    compute_cost: float
    storage_cost: float

    # Operational costs
    operational_overhead: OperationalOverhead

    # Metadata
    deployment_type: str  # "EC2" or "EKS"
    data_size_gb: float
    execution_time_seconds: float

    # Optional detailed cost models
    cost_model: EC2CostModel | EKSCostModel | None = None

    def calculate_infrastructure_cost(self) -> float:
        """Calculate total infrastructure cost.

        Returns:
            Infrastructure cost in USD
        """
        return self.compute_cost + self.storage_cost

    def calculate_first_year_tco(self) -> float:
        """Calculate first year TCO including setup and maintenance.

        Returns:
            First year TCO in USD
        """
        infrastructure = self.calculate_infrastructure_cost()
        initial_setup = self.operational_overhead.calculate_initial_setup_cost()
        annual_maintenance = (
            self.operational_overhead.calculate_annual_maintenance_cost()
        )

        return infrastructure + initial_setup + annual_maintenance

    def calculate_ongoing_annual_tco(self) -> float:
        """Calculate ongoing annual TCO (after first year).

        Returns:
            Ongoing annual TCO in USD
        """
        infrastructure = self.calculate_infrastructure_cost()
        annual_maintenance = (
            self.operational_overhead.calculate_annual_maintenance_cost()
        )

        return infrastructure + annual_maintenance

    def calculate_tco_per_gb(self) -> float:
        """Calculate TCO per GB processed (first year).

        Returns:
            TCO per GB in USD
        """
        if self.data_size_gb == 0:
            return 0.0
        return self.calculate_first_year_tco() / self.data_size_gb

    def to_dict(self) -> dict[str, Any]:
        """Convert TCO report to dictionary.

        Returns:
            Dictionary representation
        """
        result = {
            "deployment_type": self.deployment_type,
            "data_size_gb": self.data_size_gb,
            "execution_time_seconds": self.execution_time_seconds,
            "execution_time_hours": self.execution_time_seconds / 3600,
            "compute_cost": self.compute_cost,
            "storage_cost": self.storage_cost,
            "infrastructure_cost": self.calculate_infrastructure_cost(),
            "operational_overhead": self.operational_overhead.to_dict(),
            "first_year_tco": self.calculate_first_year_tco(),
            "ongoing_annual_tco": self.calculate_ongoing_annual_tco(),
            "tco_per_gb": self.calculate_tco_per_gb(),
        }

        # Include detailed cost model if available
        if self.cost_model:
            result["detailed_cost_model"] = self.cost_model.to_dict()

        return result


class TCOAnalyzer:
    """Analyzer for Total Cost of Ownership calculations."""

    # Default operational overhead estimates based on real-world experience
    EC2_OVERHEAD = OperationalOverhead(
        deployment_time_hours=2.0,  # Simple EC2 instance setup
        monitoring_setup_hours=1.0,  # CloudWatch agent setup
        debugging_complexity_hours=0.5,  # SSH and logs
        maintenance_hours_per_month=2.0,  # Minimal maintenance
        deployment_complexity=ComplexityLevel.LOW,
        monitoring_complexity=ComplexityLevel.LOW,
        debugging_complexity=ComplexityLevel.LOW,
    )

    EKS_OVERHEAD = OperationalOverhead(
        deployment_time_hours=8.0,  # EKS cluster + Spark Operator
        monitoring_setup_hours=4.0,  # Container Insights + Prometheus
        debugging_complexity_hours=3.0,  # K8s debugging, pod logs
        maintenance_hours_per_month=8.0,  # Cluster upgrades, scaling
        deployment_complexity=ComplexityLevel.HIGH,
        monitoring_complexity=ComplexityLevel.HIGH,
        debugging_complexity=ComplexityLevel.MEDIUM,
    )

    @staticmethod
    def create_ec2_tco_report(
        cost_model: EC2CostModel,
        operational_overhead: OperationalOverhead | None = None,
    ) -> TCOReport:
        """Create TCO report for EC2 deployment.

        Args:
            cost_model: EC2 cost model
            operational_overhead: Optional custom operational overhead

        Returns:
            TCO report for EC2
        """
        if operational_overhead is None:
            operational_overhead = TCOAnalyzer.EC2_OVERHEAD

        return TCOReport(
            compute_cost=cost_model.calculate_compute_cost(),
            storage_cost=cost_model.calculate_s3_cost(),
            operational_overhead=operational_overhead,
            deployment_type="EC2",
            data_size_gb=cost_model.data_size_gb,
            execution_time_seconds=cost_model.execution_time_seconds,
            cost_model=cost_model,
        )

    @staticmethod
    def create_eks_tco_report(
        cost_model: EKSCostModel,
        operational_overhead: OperationalOverhead | None = None,
    ) -> TCOReport:
        """Create TCO report for EKS deployment.

        Args:
            cost_model: EKS cost model
            operational_overhead: Optional custom operational overhead

        Returns:
            TCO report for EKS
        """
        if operational_overhead is None:
            operational_overhead = TCOAnalyzer.EKS_OVERHEAD

        compute_cost = (
            cost_model.calculate_control_plane_cost() + cost_model.calculate_node_cost()
        )

        return TCOReport(
            compute_cost=compute_cost,
            storage_cost=cost_model.calculate_s3_cost(),
            operational_overhead=operational_overhead,
            deployment_type="EKS",
            data_size_gb=cost_model.data_size_gb,
            execution_time_seconds=cost_model.execution_time_seconds,
            cost_model=cost_model,
        )

    @staticmethod
    def compare_tco(ec2_report: TCOReport, eks_report: TCOReport) -> dict[str, Any]:
        """Compare TCO between EC2 and EKS deployments.

        Args:
            ec2_report: EC2 TCO report
            eks_report: EKS TCO report

        Returns:
            Dictionary with TCO comparison metrics
        """
        ec2_first_year = ec2_report.calculate_first_year_tco()
        eks_first_year = eks_report.calculate_first_year_tco()

        ec2_ongoing = ec2_report.calculate_ongoing_annual_tco()
        eks_ongoing = eks_report.calculate_ongoing_annual_tco()

        first_year_difference = eks_first_year - ec2_first_year
        ongoing_difference = eks_ongoing - ec2_ongoing

        first_year_winner = "EC2" if ec2_first_year < eks_first_year else "EKS"
        ongoing_winner = "EC2" if ec2_ongoing < eks_ongoing else "EKS"

        first_year_savings_pct = (
            abs(first_year_difference) / max(ec2_first_year, eks_first_year) * 100
            if max(ec2_first_year, eks_first_year) > 0
            else 0
        )

        ongoing_savings_pct = (
            abs(ongoing_difference) / max(ec2_ongoing, eks_ongoing) * 100
            if max(ec2_ongoing, eks_ongoing) > 0
            else 0
        )

        return {
            "ec2_first_year_tco": ec2_first_year,
            "eks_first_year_tco": eks_first_year,
            "first_year_difference": first_year_difference,
            "first_year_winner": first_year_winner,
            "first_year_savings_pct": first_year_savings_pct,
            "ec2_ongoing_annual_tco": ec2_ongoing,
            "eks_ongoing_annual_tco": eks_ongoing,
            "ongoing_difference": ongoing_difference,
            "ongoing_winner": ongoing_winner,
            "ongoing_savings_pct": ongoing_savings_pct,
            "ec2_complexity_score": (
                ec2_report.operational_overhead.get_complexity_score()
            ),
            "eks_complexity_score": (
                eks_report.operational_overhead.get_complexity_score()
            ),
            "complexity_difference": (
                eks_report.operational_overhead.get_complexity_score()
                - ec2_report.operational_overhead.get_complexity_score()
            ),
        }

    @staticmethod
    def calculate_breakeven_point(
        ec2_report: TCOReport, eks_report: TCOReport
    ) -> dict[str, Any]:
        """Calculate the breakeven point where EKS becomes cost-effective.

        This considers both infrastructure and operational costs over time.

        Args:
            ec2_report: EC2 TCO report
            eks_report: EKS TCO report

        Returns:
            Dictionary with breakeven analysis
        """
        # Initial setup cost difference
        ec2_setup = ec2_report.operational_overhead.calculate_initial_setup_cost()
        eks_setup = eks_report.operational_overhead.calculate_initial_setup_cost()
        setup_difference = eks_setup - ec2_setup

        # Monthly cost difference
        ec2_monthly = (
            ec2_report.calculate_infrastructure_cost()
            + ec2_report.operational_overhead.calculate_monthly_maintenance_cost()
        )
        eks_monthly = (
            eks_report.calculate_infrastructure_cost()
            + eks_report.operational_overhead.calculate_monthly_maintenance_cost()
        )
        monthly_difference = eks_monthly - ec2_monthly

        # Calculate breakeven months (if EKS is cheaper per month)
        if monthly_difference < 0:  # EKS is cheaper per month
            breakeven_months = abs(setup_difference / monthly_difference)
            breakeven_message = (
                f"EKS becomes cost-effective after {breakeven_months:.1f} months"
            )
        elif monthly_difference > 0:  # EC2 is always cheaper
            breakeven_months = float("inf")
            breakeven_message = "EC2 is always more cost-effective"
        else:  # Same monthly cost
            breakeven_months = 0
            breakeven_message = "Same monthly cost, choose based on other factors"

        return {
            "setup_cost_difference": setup_difference,
            "monthly_cost_difference": monthly_difference,
            "breakeven_months": breakeven_months,
            "breakeven_message": breakeven_message,
            "ec2_monthly_cost": ec2_monthly,
            "eks_monthly_cost": eks_monthly,
        }
