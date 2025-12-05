#!/usr/bin/env python3
"""Test script for cost analysis modules.

This script validates the cost calculation, TCO analysis, and crossover
point identification functionality.
"""

import json
from pathlib import Path

from src.analysis.cost_calculator import CostCalculator, InstanceType
from src.analysis.crossover_analyzer import BenchmarkResult, CrossoverAnalyzer
from src.analysis.tco_analyzer import TCOAnalyzer


def test_cost_calculator():
    """Test cost calculator functionality."""
    print("=" * 80)
    print("Testing Cost Calculator")
    print("=" * 80)

    # Test EC2 cost calculation
    ec2_model = CostCalculator.calculate_ec2_cost(
        instance_type=InstanceType.R6I_2XLARGE,
        execution_time_seconds=300,  # 5 minutes
        data_size_gb=10.0,
        s3_read_requests=1000,
        s3_write_requests=100,
    )

    print("\nEC2 Cost Model:")
    print(json.dumps(ec2_model.to_dict(), indent=2))

    # Test EKS cost calculation
    eks_model = CostCalculator.calculate_eks_cost(
        node_instance_type=InstanceType.R6I_2XLARGE,
        num_nodes=3,
        execution_time_seconds=180,  # 3 minutes
        data_size_gb=10.0,
        num_executors=3,
        s3_read_requests=1000,
        s3_write_requests=100,
    )

    print("\nEKS Cost Model:")
    print(json.dumps(eks_model.to_dict(), indent=2))

    # Compare costs
    comparison = CostCalculator.compare_costs(ec2_model, eks_model)
    print("\nCost Comparison:")
    print(json.dumps(comparison, indent=2))

    # Test Graviton savings
    graviton_savings = CostCalculator.calculate_graviton_savings(
        InstanceType.R6I_2XLARGE, InstanceType.R7G_2XLARGE
    )
    print("\nGraviton Savings:")
    print(json.dumps(graviton_savings, indent=2))


def test_tco_analyzer():
    """Test TCO analyzer functionality."""
    print("\n" + "=" * 80)
    print("Testing TCO Analyzer")
    print("=" * 80)

    # Create cost models
    ec2_model = CostCalculator.calculate_ec2_cost(
        instance_type=InstanceType.R6I_2XLARGE,
        execution_time_seconds=300,
        data_size_gb=10.0,
    )

    eks_model = CostCalculator.calculate_eks_cost(
        node_instance_type=InstanceType.R6I_2XLARGE,
        num_nodes=3,
        execution_time_seconds=180,
        data_size_gb=10.0,
    )

    # Create TCO reports
    ec2_tco = TCOAnalyzer.create_ec2_tco_report(ec2_model)
    eks_tco = TCOAnalyzer.create_eks_tco_report(eks_model)

    print("\nEC2 TCO Report:")
    print(json.dumps(ec2_tco.to_dict(), indent=2))

    print("\nEKS TCO Report:")
    print(json.dumps(eks_tco.to_dict(), indent=2))

    # Compare TCO
    tco_comparison = TCOAnalyzer.compare_tco(ec2_tco, eks_tco)
    print("\nTCO Comparison:")
    print(json.dumps(tco_comparison, indent=2))

    # Calculate breakeven point
    breakeven = TCOAnalyzer.calculate_breakeven_point(ec2_tco, eks_tco)
    print("\nBreakeven Analysis:")
    print(json.dumps(breakeven, indent=2))


def test_crossover_analyzer():
    """Test crossover analyzer functionality."""
    print("\n" + "=" * 80)
    print("Testing Crossover Analyzer")
    print("=" * 80)

    # Create sample benchmark results
    sample_results = [
        BenchmarkResult(
            data_size="tiny",
            data_size_gb=0.1,
            polars_time_seconds=5.0,
            spark_time_seconds=25.0,
            polars_memory_mb=200,
            spark_memory_mb=300,
        ),
        BenchmarkResult(
            data_size="small",
            data_size_gb=1.2,
            polars_time_seconds=30.0,
            spark_time_seconds=40.0,
            polars_memory_mb=500,
            spark_memory_mb=600,
        ),
        BenchmarkResult(
            data_size="medium",
            data_size_gb=4.0,
            polars_time_seconds=120.0,
            spark_time_seconds=80.0,
            polars_memory_mb=2000,
            spark_memory_mb=1500,
        ),
    ]

    analyzer = CrossoverAnalyzer()

    # Analyze performance crossover
    performance = analyzer.analyze_performance_crossover(sample_results)
    print("\nPerformance Crossover Analysis:")
    print(json.dumps(performance, indent=2))

    # Analyze cost crossover
    cost = analyzer.analyze_cost_crossover(sample_results)
    print("\nCost Crossover Analysis:")
    print(json.dumps(cost, indent=2))

    # Analyze TCO crossover
    tco = analyzer.analyze_tco_crossover(sample_results)
    print("\nTCO Crossover Analysis:")
    print(json.dumps(tco, indent=2))

    # Full crossover analysis
    crossover = analyzer.analyze_crossover_point(sample_results)
    print("\nCrossover Point:")
    print(json.dumps(crossover.to_dict(), indent=2))

    # Generate decision framework
    decision_framework = analyzer.generate_decision_framework(crossover)
    print("\nDecision Framework:")
    print(json.dumps(decision_framework, indent=2))


def test_with_real_data():
    """Test with real benchmark data if available."""
    print("\n" + "=" * 80)
    print("Testing with Real Benchmark Data")
    print("=" * 80)

    results_dir = Path("benchmark_results")
    if not results_dir.exists():
        print("\nNo benchmark_results directory found. Skipping real data test.")
        return

    analyzer = CrossoverAnalyzer()

    try:
        results = analyzer.load_benchmark_results(results_dir)
        print(f"\nLoaded {len(results)} benchmark results")

        if results:
            crossover = analyzer.analyze_crossover_point(results)
            print("\nCrossover Point Analysis:")
            print(json.dumps(crossover.to_dict(), indent=2))

            decision_framework = analyzer.generate_decision_framework(crossover)
            print("\nDecision Framework Summary:")
            print(decision_framework["summary"])
    except Exception as e:
        print(f"\nError loading real data: {e}")


def main():
    """Run all tests."""
    print("Cost Analysis Module Test Suite")
    print("=" * 80)

    test_cost_calculator()
    test_tco_analyzer()
    test_crossover_analyzer()
    test_with_real_data()

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
