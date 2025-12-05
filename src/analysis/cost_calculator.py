"""Cost calculation module for ETL benchmark analysis.

This module provides cost models for EC2 and EKS deployments, including
compute costs, storage costs, and cost-per-GB-processed metrics.

Pricing is region-specific and can be configured for different AWS
regions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Regional pricing data for AWS EC2 instances (as of 2024)
# Source: AWS Pricing Calculator
REGIONAL_PRICING = {
    "us-east-1": {
        "r6i.2xlarge": 0.504,
        "r6i.4xlarge": 1.008,
        "r6i.8xlarge": 2.016,
        "r7g.2xlarge": 0.403,
        "r7g.4xlarge": 0.806,
        "r7g.8xlarge": 1.613,
    },
    "eu-central-1": {
        "r6i.2xlarge": 0.588,  # ~17% more expensive than us-east-1
        "r6i.4xlarge": 1.176,
        "r6i.8xlarge": 2.352,
        "r7g.2xlarge": 0.470,  # Graviton still ~20% cheaper
        "r7g.4xlarge": 0.941,
        "r7g.8xlarge": 1.882,
    },
    "us-west-2": {
        "r6i.2xlarge": 0.504,
        "r6i.4xlarge": 1.008,
        "r6i.8xlarge": 2.016,
        "r7g.2xlarge": 0.403,
        "r7g.4xlarge": 0.806,
        "r7g.8xlarge": 1.613,
    },
    "ap-southeast-1": {
        "r6i.2xlarge": 0.588,
        "r6i.4xlarge": 1.176,
        "r6i.8xlarge": 2.352,
        "r7g.2xlarge": 0.470,
        "r7g.4xlarge": 0.941,
        "r7g.8xlarge": 1.882,
    },
}

# Regional S3 pricing (per GB-month for Standard storage)
S3_STORAGE_PRICING = {
    "us-east-1": 0.023,
    "eu-central-1": 0.024,
    "us-west-2": 0.023,
    "ap-southeast-1": 0.025,
}

# S3 request pricing is consistent across regions
S3_GET_REQUEST_COST_PER_1K = 0.0004
S3_PUT_REQUEST_COST_PER_1K = 0.005

# EKS control plane pricing (per hour)
EKS_CONTROL_PLANE_PRICING = {
    "us-east-1": 0.10,
    "eu-central-1": 0.10,
    "us-west-2": 0.10,
    "ap-southeast-1": 0.10,
}


class InstanceType(Enum):
    """AWS EC2 instance types with specifications.

    Pricing is region-specific and retrieved via
    get_hourly_rate(region).
    """

    # Intel x86 instances
    R6I_2XLARGE = ("r6i.2xlarge", 8, 64, "x86")
    R6I_4XLARGE = ("r6i.4xlarge", 16, 128, "x86")
    R6I_8XLARGE = ("r6i.8xlarge", 32, 256, "x86")

    # Graviton ARM instances (typically ~20% cheaper)
    R7G_2XLARGE = ("r7g.2xlarge", 8, 64, "arm")
    R7G_4XLARGE = ("r7g.4xlarge", 16, 128, "arm")
    R7G_8XLARGE = ("r7g.8xlarge", 32, 256, "arm")

    def __init__(
        self,
        instance_name: str,
        vcpus: int,
        memory_gb: int,
        architecture: str,
    ):
        self.instance_name = instance_name
        self.vcpus = vcpus
        self.memory_gb = memory_gb
        self.architecture = architecture

    def get_hourly_rate(self, region: str = "us-east-1") -> float:
        """Get hourly rate for this instance type in the specified region.

        Args:
            region: AWS region (default: us-east-1)

        Returns:
            Hourly rate in USD

        Raises:
            ValueError: If region or instance type is not supported
        """
        if region not in REGIONAL_PRICING:
            raise ValueError(
                f"Region '{region}' not supported. "
                f"Supported regions: {list(REGIONAL_PRICING.keys())}"
            )

        if self.instance_name not in REGIONAL_PRICING[region]:
            raise ValueError(
                f"Instance type '{self.instance_name}' not available in region"
                f" '{region}'"
            )

        return REGIONAL_PRICING[region][self.instance_name]


@dataclass
class EC2CostModel:
    """Cost model for EC2 deployment."""

    instance_type: InstanceType
    execution_time_seconds: float
    data_size_gb: float
    region: str = "us-east-1"
    s3_read_requests: int = 0
    s3_write_requests: int = 0
    s3_storage_gb_month: float = 0.0

    def calculate_compute_cost(self) -> float:
        """Calculate EC2 compute cost.

        Returns:
            Compute cost in USD
        """
        execution_hours = self.execution_time_seconds / 3600
        hourly_rate = self.instance_type.get_hourly_rate(self.region)
        return hourly_rate * execution_hours

    def calculate_s3_cost(self) -> float:
        """Calculate S3 costs (requests + storage).

        S3 Pricing (region-specific):
        - GET requests: $0.0004 per 1,000 requests (all regions)
        - PUT requests: $0.005 per 1,000 requests (all regions)
        - Storage: Region-specific per GB-month (Standard)

        Returns:
            S3 cost in USD
        """
        get_cost = (self.s3_read_requests / 1000) * S3_GET_REQUEST_COST_PER_1K
        put_cost = (self.s3_write_requests / 1000) * S3_PUT_REQUEST_COST_PER_1K

        storage_rate = S3_STORAGE_PRICING.get(self.region, 0.023)
        storage_cost = self.s3_storage_gb_month * storage_rate

        return get_cost + put_cost + storage_cost

    def calculate_total_cost(self) -> float:
        """Calculate total EC2 deployment cost.

        Returns:
            Total cost in USD
        """
        return self.calculate_compute_cost() + self.calculate_s3_cost()

    def calculate_cost_per_gb(self) -> float:
        """Calculate cost per GB processed.

        Returns:
            Cost per GB in USD
        """
        if self.data_size_gb == 0:
            return 0.0
        return self.calculate_total_cost() / self.data_size_gb

    def to_dict(self) -> dict[str, Any]:
        """Convert cost model to dictionary.

        Returns:
            Dictionary representation of cost model
        """
        return {
            "region": self.region,
            "instance_type": self.instance_type.instance_name,
            "architecture": self.instance_type.architecture,
            "vcpus": self.instance_type.vcpus,
            "memory_gb": self.instance_type.memory_gb,
            "hourly_rate": self.instance_type.get_hourly_rate(self.region),
            "execution_time_seconds": self.execution_time_seconds,
            "execution_time_hours": self.execution_time_seconds / 3600,
            "data_size_gb": self.data_size_gb,
            "compute_cost": self.calculate_compute_cost(),
            "s3_cost": self.calculate_s3_cost(),
            "total_cost": self.calculate_total_cost(),
            "cost_per_gb": self.calculate_cost_per_gb(),
        }


@dataclass
class EKSCostModel:
    """Cost model for EKS deployment."""

    node_instance_type: InstanceType
    num_nodes: int
    execution_time_seconds: float
    data_size_gb: float
    region: str = "us-east-1"
    num_executors: int = 0
    s3_read_requests: int = 0
    s3_write_requests: int = 0
    s3_storage_gb_month: float = 0.0

    def calculate_control_plane_cost(self) -> float:
        """Calculate EKS control plane cost.

        Returns:
            Control plane cost in USD
        """
        execution_hours = self.execution_time_seconds / 3600
        control_plane_rate = EKS_CONTROL_PLANE_PRICING.get(self.region, 0.10)
        return control_plane_rate * execution_hours

    def calculate_node_cost(self) -> float:
        """Calculate EKS node compute cost.

        Returns:
            Node compute cost in USD
        """
        execution_hours = self.execution_time_seconds / 3600
        hourly_rate = self.node_instance_type.get_hourly_rate(self.region)
        return hourly_rate * self.num_nodes * execution_hours

    def calculate_s3_cost(self) -> float:
        """Calculate S3 costs (requests + storage).

        S3 Pricing (region-specific):
        - GET requests: $0.0004 per 1,000 requests (all regions)
        - PUT requests: $0.005 per 1,000 requests (all regions)
        - Storage: Region-specific per GB-month (Standard)

        Returns:
            S3 cost in USD
        """
        get_cost = (self.s3_read_requests / 1000) * S3_GET_REQUEST_COST_PER_1K
        put_cost = (self.s3_write_requests / 1000) * S3_PUT_REQUEST_COST_PER_1K

        storage_rate = S3_STORAGE_PRICING.get(self.region, 0.023)
        storage_cost = self.s3_storage_gb_month * storage_rate

        return get_cost + put_cost + storage_cost

    def calculate_total_cost(self) -> float:
        """Calculate total EKS deployment cost.

        Returns:
            Total cost in USD
        """
        return (
            self.calculate_control_plane_cost()
            + self.calculate_node_cost()
            + self.calculate_s3_cost()
        )

    def calculate_cost_per_gb(self) -> float:
        """Calculate cost per GB processed.

        Returns:
            Cost per GB in USD
        """
        if self.data_size_gb == 0:
            return 0.0
        return self.calculate_total_cost() / self.data_size_gb

    def to_dict(self) -> dict[str, Any]:
        """Convert cost model to dictionary.

        Returns:
            Dictionary representation of cost model
        """
        return {
            "region": self.region,
            "node_instance_type": self.node_instance_type.instance_name,
            "architecture": self.node_instance_type.architecture,
            "vcpus_per_node": self.node_instance_type.vcpus,
            "memory_gb_per_node": self.node_instance_type.memory_gb,
            "node_hourly_rate": self.node_instance_type.get_hourly_rate(self.region),
            "num_nodes": self.num_nodes,
            "num_executors": self.num_executors,
            "execution_time_seconds": self.execution_time_seconds,
            "execution_time_hours": self.execution_time_seconds / 3600,
            "data_size_gb": self.data_size_gb,
            "control_plane_cost": self.calculate_control_plane_cost(),
            "node_cost": self.calculate_node_cost(),
            "s3_cost": self.calculate_s3_cost(),
            "total_cost": self.calculate_total_cost(),
            "cost_per_gb": self.calculate_cost_per_gb(),
        }


class CostCalculator:
    """Main cost calculator for comparing EC2 and EKS deployments."""

    @staticmethod
    def calculate_ec2_cost(
        instance_type: InstanceType,
        execution_time_seconds: float,
        data_size_gb: float,
        region: str = "us-east-1",
        s3_read_requests: int = 0,
        s3_write_requests: int = 0,
        s3_storage_gb_month: float = 0.0,
    ) -> EC2CostModel:
        """Calculate EC2 deployment cost.

        Args:
            instance_type: EC2 instance type
            execution_time_seconds: Execution time in seconds
            data_size_gb: Data size processed in GB
            region: AWS region (default: us-east-1)
            s3_read_requests: Number of S3 GET requests
            s3_write_requests: Number of S3 PUT requests
            s3_storage_gb_month: S3 storage in GB-months

        Returns:
            EC2 cost model with calculated costs
        """
        return EC2CostModel(
            instance_type=instance_type,
            execution_time_seconds=execution_time_seconds,
            data_size_gb=data_size_gb,
            region=region,
            s3_read_requests=s3_read_requests,
            s3_write_requests=s3_write_requests,
            s3_storage_gb_month=s3_storage_gb_month,
        )

    @staticmethod
    def calculate_eks_cost(
        node_instance_type: InstanceType,
        num_nodes: int,
        execution_time_seconds: float,
        data_size_gb: float,
        region: str = "us-east-1",
        num_executors: int = 0,
        s3_read_requests: int = 0,
        s3_write_requests: int = 0,
        s3_storage_gb_month: float = 0.0,
    ) -> EKSCostModel:
        """Calculate EKS deployment cost.

        Args:
            node_instance_type: EKS node instance type
            num_nodes: Number of nodes in cluster
            execution_time_seconds: Execution time in seconds
            data_size_gb: Data size processed in GB
            region: AWS region (default: us-east-1)
            num_executors: Number of Spark executors
            s3_read_requests: Number of S3 GET requests
            s3_write_requests: Number of S3 PUT requests
            s3_storage_gb_month: S3 storage in GB-months

        Returns:
            EKS cost model with calculated costs
        """
        return EKSCostModel(
            node_instance_type=node_instance_type,
            num_nodes=num_nodes,
            execution_time_seconds=execution_time_seconds,
            data_size_gb=data_size_gb,
            region=region,
            num_executors=num_executors,
            s3_read_requests=s3_read_requests,
            s3_write_requests=s3_write_requests,
            s3_storage_gb_month=s3_storage_gb_month,
        )

    @staticmethod
    def compare_costs(
        ec2_model: EC2CostModel, eks_model: EKSCostModel
    ) -> dict[str, Any]:
        """Compare EC2 and EKS costs.

        Args:
            ec2_model: EC2 cost model
            eks_model: EKS cost model

        Returns:
            Dictionary with cost comparison metrics
        """
        ec2_total = ec2_model.calculate_total_cost()
        eks_total = eks_model.calculate_total_cost()

        cost_difference = eks_total - ec2_total
        cost_ratio = eks_total / ec2_total if ec2_total > 0 else 0

        winner = "EC2" if ec2_total < eks_total else "EKS"
        savings_pct = (
            abs(cost_difference) / max(ec2_total, eks_total) * 100
            if max(ec2_total, eks_total) > 0
            else 0
        )

        return {
            "ec2_total_cost": ec2_total,
            "eks_total_cost": eks_total,
            "cost_difference": cost_difference,
            "cost_ratio": cost_ratio,
            "winner": winner,
            "savings_pct": savings_pct,
            "ec2_cost_per_gb": ec2_model.calculate_cost_per_gb(),
            "eks_cost_per_gb": eks_model.calculate_cost_per_gb(),
        }

    @staticmethod
    def calculate_graviton_savings(
        x86_instance: InstanceType,
        arm_instance: InstanceType,
        region: str = "us-east-1",
    ) -> dict[str, Any]:
        """Calculate cost savings from using Graviton (ARM) instances.

        Args:
            x86_instance: x86 instance type
            arm_instance: ARM (Graviton) instance type
            region: AWS region (default: us-east-1)

        Returns:
            Dictionary with Graviton savings analysis
        """
        x86_rate = x86_instance.get_hourly_rate(region)
        arm_rate = arm_instance.get_hourly_rate(region)

        hourly_savings = x86_rate - arm_rate
        savings_pct = (hourly_savings / x86_rate) * 100 if x86_rate > 0 else 0

        return {
            "region": region,
            "x86_instance": x86_instance.instance_name,
            "x86_hourly_rate": x86_rate,
            "arm_instance": arm_instance.instance_name,
            "arm_hourly_rate": arm_rate,
            "hourly_savings": hourly_savings,
            "savings_pct": savings_pct,
        }

    @staticmethod
    def get_supported_regions() -> list[str]:
        """Get list of supported AWS regions.

        Returns:
            List of supported region names
        """
        return list(REGIONAL_PRICING.keys())

    @staticmethod
    def get_region_pricing_info(region: str) -> dict[str, Any]:
        """Get pricing information for a specific region.

        Args:
            region: AWS region

        Returns:
            Dictionary with region pricing details

        Raises:
            ValueError: If region is not supported
        """
        if region not in REGIONAL_PRICING:
            raise ValueError(
                f"Region '{region}' not supported. "
                f"Supported regions: {list(REGIONAL_PRICING.keys())}"
            )

        return {
            "region": region,
            "instance_pricing": REGIONAL_PRICING[region],
            "s3_storage_rate": S3_STORAGE_PRICING.get(region, 0.023),
            "s3_get_request_rate_per_1k": S3_GET_REQUEST_COST_PER_1K,
            "s3_put_request_rate_per_1k": S3_PUT_REQUEST_COST_PER_1K,
            "eks_control_plane_rate": EKS_CONTROL_PLANE_PRICING.get(region, 0.10),
        }
