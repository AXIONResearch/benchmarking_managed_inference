#!/usr/bin/env python3
"""
Compare Benchmark Results

Compares baseline vs managed inference performance and generates reports.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import argparse


def load_latest_metrics(env: str) -> Dict:
    """Load the most recent metrics file for an environment."""
    results_dir = Path(f"results/{env}")

    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        sys.exit(1)

    metrics_files = sorted(results_dir.glob("metrics_*.json"), reverse=True)

    if not metrics_files:
        print(f"Error: No metrics files found in {results_dir}")
        sys.exit(1)

    with open(metrics_files[0]) as f:
        return json.load(f)


def calculate_improvement(baseline: float, managed: float) -> float:
    """Calculate percentage improvement."""
    if baseline == 0:
        return 0
    return ((baseline - managed) / baseline) * 100


def print_comparison(baseline_metrics: Dict, managed_metrics: Dict):
    """Print comparison report."""
    print("\n" + "=" * 80)
    print("BASELINE vs MANAGED COMPARISON")
    print("=" * 80)

    # Throughput comparison
    print("\nTHROUGHPUT")
    print("-" * 80)
    baseline_rps = baseline_metrics['requests_per_sec']
    managed_rps = managed_metrics['requests_per_sec']
    rps_improvement = calculate_improvement(baseline_rps, managed_rps) * -1  # Higher is better

    print(f"Requests/sec:")
    print(f"  Baseline: {baseline_rps:.2f}")
    print(f"  Managed:  {managed_rps:.2f}")
    print(f"  Change:   {rps_improvement:+.2f}%")

    baseline_tps = baseline_metrics['throughput']['tokens_per_sec']
    managed_tps = managed_metrics['throughput']['tokens_per_sec']
    tps_improvement = calculate_improvement(baseline_tps, managed_tps) * -1

    print(f"\nTokens/sec:")
    print(f"  Baseline: {baseline_tps:.2f}")
    print(f"  Managed:  {managed_tps:.2f}")
    print(f"  Change:   {tps_improvement:+.2f}%")

    # TTFT comparison
    print("\nTIME TO FIRST TOKEN (lower is better)")
    print("-" * 80)
    for percentile in ['p50', 'p90', 'p99', 'mean']:
        baseline_val = baseline_metrics['ttft'][percentile]
        managed_val = managed_metrics['ttft'][percentile]
        improvement = calculate_improvement(baseline_val, managed_val)

        print(f"{percentile.upper()}:")
        print(f"  Baseline: {baseline_val:.3f}s")
        print(f"  Managed:  {managed_val:.3f}s")
        print(f"  Change:   {improvement:+.2f}%")

    # Latency comparison
    print("\nEND-TO-END LATENCY (lower is better)")
    print("-" * 80)
    for percentile in ['p50', 'p90', 'p99', 'mean']:
        baseline_val = baseline_metrics['latency'][percentile]
        managed_val = managed_metrics['latency'][percentile]
        improvement = calculate_improvement(baseline_val, managed_val)

        print(f"{percentile.upper()}:")
        print(f"  Baseline: {baseline_val:.3f}s")
        print(f"  Managed:  {managed_val:.3f}s")
        print(f"  Change:   {improvement:+.2f}%")

    # Success rate comparison
    print("\nRELIABILITY")
    print("-" * 80)
    baseline_success = (baseline_metrics['successful_requests'] / baseline_metrics['total_requests']) * 100
    managed_success = (managed_metrics['successful_requests'] / managed_metrics['total_requests']) * 100

    print(f"Success Rate:")
    print(f"  Baseline: {baseline_success:.2f}%")
    print(f"  Managed:  {managed_success:.2f}%")
    print(f"  Change:   {managed_success - baseline_success:+.2f}%")

    print("\n" + "=" * 80)

    # Summary
    print("\nSUMMARY")
    print("-" * 80)

    improvements = {
        "Throughput (req/s)": rps_improvement,
        "Throughput (tok/s)": tps_improvement,
        "TTFT P50": calculate_improvement(baseline_metrics['ttft']['p50'], managed_metrics['ttft']['p50']),
        "TTFT P99": calculate_improvement(baseline_metrics['ttft']['p99'], managed_metrics['ttft']['p99']),
        "Latency P50": calculate_improvement(baseline_metrics['latency']['p50'], managed_metrics['latency']['p50']),
        "Latency P99": calculate_improvement(baseline_metrics['latency']['p99'], managed_metrics['latency']['p99']),
    }

    for metric, improvement in improvements.items():
        symbol = "✓" if improvement > 0 else "✗"
        print(f"{symbol} {metric:20s}: {improvement:+6.2f}%")

    print("=" * 80 + "\n")


def save_comparison_report(baseline_metrics: Dict, managed_metrics: Dict, output_file: Path):
    """Save comparison report as JSON."""
    report = {
        "baseline": baseline_metrics,
        "managed": managed_metrics,
        "improvements": {
            "throughput_rps": calculate_improvement(
                baseline_metrics['requests_per_sec'],
                managed_metrics['requests_per_sec']
            ) * -1,
            "throughput_tps": calculate_improvement(
                baseline_metrics['throughput']['tokens_per_sec'],
                managed_metrics['throughput']['tokens_per_sec']
            ) * -1,
            "ttft_p50": calculate_improvement(
                baseline_metrics['ttft']['p50'],
                managed_metrics['ttft']['p50']
            ),
            "ttft_p99": calculate_improvement(
                baseline_metrics['ttft']['p99'],
                managed_metrics['ttft']['p99']
            ),
            "latency_p50": calculate_improvement(
                baseline_metrics['latency']['p50'],
                managed_metrics['latency']['p50']
            ),
            "latency_p99": calculate_improvement(
                baseline_metrics['latency']['p99'],
                managed_metrics['latency']['p99']
            ),
        }
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Comparison report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Compare benchmark results')
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('analysis/comparison_report.json'),
        help='Output file for comparison report (default: analysis/comparison_report.json)'
    )

    args = parser.parse_args()

    # Load metrics
    baseline_metrics = load_latest_metrics('baseline')
    managed_metrics = load_latest_metrics('managed')

    # Print comparison
    print_comparison(baseline_metrics, managed_metrics)

    # Save report
    save_comparison_report(baseline_metrics, managed_metrics, args.output)


if __name__ == "__main__":
    main()
