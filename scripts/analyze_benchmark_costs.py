#!/usr/bin/env python3
"""Analyze benchmark costs and generate cost reports.

This script analyzes benchmark results and generates comprehensive cost
analysis including infrastructure costs, TCO, and crossover point
identification.
"""

import argparse
import json
import sys
from pathlib import Path

from src.analysis.cost_calculator import InstanceType
from src.analysis.crossover_analyzer import CrossoverAnalyzer


def main():
    """Main entry point for cost analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze benchmark costs and identify crossover points"
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("benchmark_results"),
        help="Directory containing benchmark result JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("cost_analysis_report.json"),
        help="Output file for cost analysis report",
    )
    parser.add_argument(
        "--ec2-instance",
        type=str,
        default="R6I_2XLARGE",
        choices=[i.name for i in InstanceType],
        help="EC2 instance type for Polars",
    )
    parser.add_argument(
        "--eks-instance",
        type=str,
        default="R6I_2XLARGE",
        choices=[i.name for i in InstanceType],
        help="EKS node instance type for Spark",
    )
    parser.add_argument(
        "--eks-nodes",
        type=int,
        default=3,
        help="Number of EKS nodes",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        choices=["us-east-1", "eu-central-1", "us-west-2", "ap-southeast-1"],
        help="AWS region for pricing (default: us-east-1)",
    )

    args = parser.parse_args()

    # Validate results directory
    if not args.results_dir.exists():
        print(f"Error: Results directory not found: {args.results_dir}")
        return 1

    # Create analyzer
    ec2_instance = InstanceType[args.ec2_instance]
    eks_instance = InstanceType[args.eks_instance]

    analyzer = CrossoverAnalyzer(
        ec2_instance_type=ec2_instance,
        eks_node_instance_type=eks_instance,
        eks_num_nodes=args.eks_nodes,
        region=args.region,
    )

    print("=" * 80)
    print("ETL Benchmark Cost Analysis")
    print("=" * 80)
    print("\nConfiguration:")
    print(f"  Region: {args.region}")
    print(f"  EC2 Instance: {ec2_instance.instance_name}")
    print(f"  EC2 Hourly Rate: ${ec2_instance.get_hourly_rate(args.region):.3f}")
    print(f"  EKS Instance: {eks_instance.instance_name}")
    print(f"  EKS Hourly Rate: ${eks_instance.get_hourly_rate(args.region):.3f}")
    print(f"  EKS Nodes: {args.eks_nodes}")
    print(f"  Results Directory: {args.results_dir}")

    # Load benchmark results
    print(f"\nLoading benchmark results from {args.results_dir}...")
    try:
        results = analyzer.load_benchmark_results(args.results_dir)
        print(f"Loaded {len(results)} benchmark results")
    except Exception as e:
        print(f"Error loading benchmark results: {e}")
        return 1

    if not results:
        print("No benchmark results found!")
        return 1

    # Analyze crossover point
    print("\nAnalyzing crossover points...")
    crossover = analyzer.analyze_crossover_point(results)

    # Generate decision framework
    print("\nGenerating decision framework...")
    decision_framework = analyzer.generate_decision_framework(crossover)

    # Create comprehensive report
    report = {
        "configuration": {
            "region": args.region,
            "ec2_instance": ec2_instance.instance_name,
            "ec2_hourly_rate": ec2_instance.get_hourly_rate(args.region),
            "eks_instance": eks_instance.instance_name,
            "eks_hourly_rate": eks_instance.get_hourly_rate(args.region),
            "eks_num_nodes": args.eks_nodes,
        },
        "crossover_analysis": crossover.to_dict(),
        "decision_framework": decision_framework,
    }

    # Save report
    print(f"\nSaving report to {args.output}...")
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("COST ANALYSIS SUMMARY")
    print("=" * 80)
    print(decision_framework["summary"])

    print("\n" + "=" * 80)
    print("CROSSOVER POINTS")
    print("=" * 80)
    print(f"\nPerformance: {crossover.performance_crossover_message}")
    print(f"Cost: {crossover.cost_crossover_message}")
    print(f"TCO: {crossover.tco_crossover_message}")

    print("\n" + "=" * 80)
    print(f"Full report saved to: {args.output}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
