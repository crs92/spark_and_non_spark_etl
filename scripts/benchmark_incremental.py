#!/usr/bin/env python3
"""Simple Incremental ETL Benchmark.

Compares Spark vs Polars performance across incremental pipeline steps.
Can run locally or on Kubernetes.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.polars_etl import run_polars_etl
from src.etl.spark_etl_incremental import run_spark_etl


def run_benchmark(input_path: str, steps: int = 5, output_dir: str = "data/benchmarks"):
    """Run benchmark comparing Spark and Polars.

    Args:
        input_path: Path to input CSV file
        steps: Number of pipeline steps to run (1-5)
        output_dir: Directory to save results
    """
    print("=" * 80)
    print("INCREMENTAL ETL BENCHMARK")
    print("=" * 80)
    print(f"Input: {input_path}")
    print(f"Steps: 1-{steps}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Run Polars ETL
    print("\n" + "=" * 80)
    print("RUNNING POLARS ETL")
    print("=" * 80)
    polars_metrics = run_polars_etl(
        input_path=input_path, output_path=str(output_path / "polars"), steps=steps
    )

    # Run Spark ETL
    print("\n" + "=" * 80)
    print("RUNNING SPARK ETL")
    print("=" * 80)
    spark_metrics = run_spark_etl(
        input_path=input_path, output_path=str(output_path / "spark"), steps=steps
    )

    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    print(f"\n{'Metric':<30} {'Polars':<15} {'Spark':<15} {'Winner':<10}")
    print("-" * 70)

    # Total time
    polars_total = polars_metrics["total_time"]
    spark_total = spark_metrics["total_time"]
    winner = "Polars" if polars_total < spark_total else "Spark"
    print(
        f"{'Total Time (s)':<30} {polars_total:<15.2f} {spark_total:<15.2f} {winner:<10}"
    )

    # Step-by-step comparison
    for step in [
        "step_1_read",
        "step_2_transform",
        "step_3_load",
        "step_4_merge",
        "step_5_additional",
    ]:
        if step in polars_metrics["steps"] and step in spark_metrics["steps"]:
            polars_time = polars_metrics["steps"][step]
            spark_time = spark_metrics["steps"][step]

            if polars_time > 0 or spark_time > 0:  # Only show if step was executed
                winner = "Polars" if polars_time < spark_time else "Spark"
                step_name = step.replace("_", " ").title()
                print(
                    f"{step_name:<30} {polars_time:<15.2f} {spark_time:<15.2f} {winner:<10}"
                )

    # Records processed
    print(
        f"{'Records Processed':<30} {polars_metrics['records_processed']:<15,} {spark_metrics['records_processed']:<15,}"
    )

    # Performance advantage
    if polars_total < spark_total:
        advantage = ((spark_total - polars_total) / spark_total) * 100
        print(f"\n✓ Polars is {advantage:.1f}% faster")
    else:
        advantage = ((polars_total - spark_total) / polars_total) * 100
        print(f"\n✓ Spark is {advantage:.1f}% faster")

    print("=" * 80)

    # Save results to JSON
    results = {
        "metadata": {
            "input_path": input_path,
            "steps": steps,
            "timestamp": datetime.now().isoformat(),
        },
        "polars": polars_metrics,
        "spark": spark_metrics,
        "comparison": {
            "polars_faster": polars_total < spark_total,
            "advantage_pct": advantage,
            "winner": winner,
        },
    }

    results_file = (
        output_path
        / f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Incremental ETL Benchmark - Compare Spark vs Polars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all 5 steps
  python benchmark_incremental.py --input data/generated/test_data.csv

  # Run only first 3 steps
  python benchmark_incremental.py --input data/generated/test_data.csv --steps 3

  # Specify output directory
  python benchmark_incremental.py --input data/input/data.csv --output results/
        """,
    )

    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument(
        "--steps",
        type=int,
        default=5,
        choices=[1, 2, 3, 4, 5],
        help="Number of pipeline steps to run (default: 5)",
    )
    parser.add_argument(
        "--output",
        default="data/benchmarks",
        help="Output directory for results (default: data/benchmarks)",
    )

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # Run benchmark
    run_benchmark(input_path=args.input, steps=args.steps, output_dir=args.output)


if __name__ == "__main__":
    main()
