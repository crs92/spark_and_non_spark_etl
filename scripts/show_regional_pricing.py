#!/usr/bin/env python3
"""Display AWS pricing information for all supported regions.

This script shows EC2 instance pricing, S3 pricing, and EKS control
plane costs across all supported AWS regions.
"""

import argparse

from src.analysis.cost_calculator import CostCalculator, InstanceType


def main():
    """Display regional pricing information."""
    parser = argparse.ArgumentParser(
        description="Display AWS pricing for all supported regions"
    )
    parser.add_argument(
        "--region",
        type=str,
        help="Show pricing for specific region only",
    )
    parser.add_argument(
        "--instance",
        type=str,
        choices=[i.name for i in InstanceType],
        help="Show pricing for specific instance type only",
    )

    args = parser.parse_args()

    regions = [args.region] if args.region else CostCalculator.get_supported_regions()

    instances = [InstanceType[args.instance]] if args.instance else list(InstanceType)

    print("=" * 80)
    print("AWS Regional Pricing Information")
    print("=" * 80)

    for region in regions:
        print(f"\n{'=' * 80}")
        print(f"Region: {region.upper()}")
        print("=" * 80)

        # Get region pricing info
        try:
            pricing_info = CostCalculator.get_region_pricing_info(region)
        except ValueError as e:
            print(f"Error: {e}")
            continue

        # EC2 Instance Pricing
        print("\nEC2 Instance Pricing (per hour):")
        print("-" * 80)
        print(
            f"{'Instance Type':<20} {'Architecture':<12} {'vCPUs':<8} {'Memory':<10} {'Rate':<10}"
        )
        print("-" * 80)

        for instance in instances:
            try:
                rate = instance.get_hourly_rate(region)
                print(
                    f"{instance.instance_name:<20} "
                    f"{instance.architecture:<12} "
                    f"{instance.vcpus:<8} "
                    f"{instance.memory_gb}GB{'':<6} "
                    f"${rate:.3f}"
                )
            except ValueError:
                print(
                    f"{instance.instance_name:<20} "
                    f"{instance.architecture:<12} "
                    f"{instance.vcpus:<8} "
                    f"{instance.memory_gb}GB{'':<6} "
                    "N/A"
                )

        # Graviton Savings
        print("\nGraviton (ARM) Savings:")
        print("-" * 80)
        graviton_pairs = [
            (InstanceType.R6I_2XLARGE, InstanceType.R7G_2XLARGE),
            (InstanceType.R6I_4XLARGE, InstanceType.R7G_4XLARGE),
            (InstanceType.R6I_8XLARGE, InstanceType.R7G_8XLARGE),
        ]

        for x86, arm in graviton_pairs:
            try:
                savings = CostCalculator.calculate_graviton_savings(x86, arm, region)
                print(
                    f"{x86.instance_name} → {arm.instance_name}: "
                    f"${savings['hourly_savings']:.3f}/hr "
                    f"({savings['savings_pct']:.1f}% savings)"
                )
            except ValueError:
                pass

        # S3 and EKS Pricing
        print("\nS3 Pricing:")
        print("-" * 80)
        print(f"Storage (Standard): ${pricing_info['s3_storage_rate']:.3f}/GB-month")
        print(
            f"GET Requests: ${pricing_info['s3_get_request_rate_per_1k']:.4f} per 1,000"
        )
        print(
            f"PUT Requests: ${pricing_info['s3_put_request_rate_per_1k']:.3f} per 1,000"
        )

        print("\nEKS Pricing:")
        print("-" * 80)
        print(f"Control Plane: ${pricing_info['eks_control_plane_rate']:.2f}/hour")

    # Cost comparison example
    if not args.region and not args.instance:
        print("\n" + "=" * 80)
        print("Example: 5-minute job processing 10GB")
        print("=" * 80)

        for region in CostCalculator.get_supported_regions():
            ec2_cost = CostCalculator.calculate_ec2_cost(
                instance_type=InstanceType.R6I_2XLARGE,
                execution_time_seconds=300,
                data_size_gb=10.0,
                region=region,
            )

            eks_cost = CostCalculator.calculate_eks_cost(
                node_instance_type=InstanceType.R6I_2XLARGE,
                num_nodes=3,
                execution_time_seconds=180,
                data_size_gb=10.0,
                region=region,
            )

            print(f"\n{region}:")
            print(f"  EC2 (r6i.2xlarge): ${ec2_cost.calculate_total_cost():.4f}")
            print(f"  EKS (3x r6i.2xlarge): ${eks_cost.calculate_total_cost():.4f}")
            print(
                "  EKS Premium:"
                f" {(eks_cost.calculate_total_cost() / ec2_cost.calculate_total_cost()):.1f}x"
            )

    print("\n" + "=" * 80)
    print("Note: Prices are approximate and may vary. Check AWS Pricing Calculator")
    print("for the most up-to-date pricing information.")
    print("=" * 80)


if __name__ == "__main__":
    main()
