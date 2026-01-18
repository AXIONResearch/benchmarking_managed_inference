#!/usr/bin/env python3
"""
Convert GenAI-Perf output to dashboard-compatible format
Reads GenAI-Perf JSON/CSV results and converts to the format expected by the dashboard
"""

import json
import csv
import sys
import os
from pathlib import Path
import argparse

def parse_genai_perf_csv(csv_file):
    """Parse GenAI-Perf profile_export.csv file"""
    if not os.path.exists(csv_file):
        return None

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return None

    # Extract metrics from CSV
    # GenAI-Perf CSV typically has columns like:
    # request_latency_ms, time_to_first_token_ms, inter_token_latency_ms, output_token_count, etc.

    latencies = []
    output_tokens = []

    for row in rows:
        # Try different column name variations
        latency_col = None
        for col_name in ['request_latency_ms', 'end_to_end_latency_ms', 'latency_ms']:
            if col_name in row:
                latency_col = col_name
                break

        if latency_col and row[latency_col]:
            try:
                # Convert ms to seconds
                latencies.append(float(row[latency_col]) / 1000.0)
            except ValueError:
                continue

        # Extract output tokens
        token_col = None
        for col_name in ['output_token_count', 'num_output_tokens', 'output_tokens']:
            if col_name in row:
                token_col = col_name
                break

        if token_col and row[token_col]:
            try:
                output_tokens.append(int(float(row[token_col])))
            except ValueError:
                continue

    if not latencies:
        return None

    # Calculate statistics
    latencies.sort()
    n = len(latencies)

    result = {
        'latencies': latencies,
        'output_tokens': output_tokens,
        'mean_latency': sum(latencies) / n,
        'median_latency': latencies[n // 2],
        'min_latency': min(latencies),
        'max_latency': max(latencies),
        'p95_latency': latencies[int(n * 0.95)],
        'p99_latency': latencies[int(n * 0.99)],
        'total_tokens': sum(output_tokens) if output_tokens else 0,
        'mean_tokens': sum(output_tokens) / len(output_tokens) if output_tokens else 0,
        'num_requests': n
    }

    return result

def parse_genai_perf_json(json_file):
    """Parse GenAI-Perf profile_export.json file"""
    if not os.path.exists(json_file):
        return None

    with open(json_file, 'r') as f:
        data = json.load(f)

    # GenAI-Perf JSON structure varies, try to extract key metrics
    # Typically under 'profile' or at root level

    metrics = data.get('profile', data)

    result = {}

    # Try to extract throughput
    if 'request_throughput' in metrics:
        result['requests_per_second'] = metrics['request_throughput']
    elif 'throughput' in metrics:
        result['requests_per_second'] = metrics['throughput']

    # Try to extract latencies
    if 'latency' in metrics:
        lat = metrics['latency']
        if isinstance(lat, dict):
            result['mean_latency'] = lat.get('mean', 0)
            result['median_latency'] = lat.get('median', lat.get('p50', 0))
            result['p95_latency'] = lat.get('p95', 0)
            result['p99_latency'] = lat.get('p99', 0)

    return result if result else None

def convert_results(genai_perf_dir, namespace="baseline"):
    """Convert all GenAI-Perf results in a directory to dashboard format"""
    genai_perf_path = Path(genai_perf_dir)

    if not genai_perf_path.exists():
        print(f"ERROR: Directory not found: {genai_perf_dir}")
        return None

    models = {
        "Llama-3.1-8B-Instruct": "meta-llama/Llama-3.1-8B-Instruct",
        "Qwen2.5-7B-Instruct": "Qwen/Qwen2.5-7B-Instruct",
        "Mistral-7B-Instruct-v0.3": "mistralai/Mistral-7B-Instruct-v0.3"
    }

    service_map = {
        "meta-llama/Llama-3.1-8B-Instruct": f"http://vllm-llama-8b.{namespace}.svc.cluster.local:8000/v1",
        "Qwen/Qwen2.5-7B-Instruct": f"http://vllm-qwen-7b.{namespace}.svc.cluster.local:8000/v1",
        "mistralai/Mistral-7B-Instruct-v0.3": f"http://vllm-mistral-7b.{namespace}.svc.cluster.local:8000/v1"
    }

    all_results = []

    # Scan for model result directories
    for model_dir in genai_perf_path.iterdir():
        if not model_dir.is_dir():
            continue

        model_short_name = model_dir.name
        full_model_name = models.get(model_short_name)

        if not full_model_name:
            print(f"Skipping unknown model directory: {model_short_name}")
            continue

        print(f"\nProcessing {full_model_name}...")

        # Look for GenAI-Perf output files
        csv_file = model_dir / "profile_export.csv"
        json_file = model_dir / "profile_export.json"

        # Try CSV first (more detailed)
        stats = parse_genai_perf_csv(csv_file)

        # Supplement with JSON data if available
        json_stats = parse_genai_perf_json(json_file)
        if json_stats:
            if stats:
                stats.update(json_stats)
            else:
                stats = json_stats

        if not stats:
            print(f"  ⚠ No valid results found in {model_dir}")
            continue

        # Calculate total time from latencies if not provided
        if 'latencies' in stats:
            # Rough estimate: total_time ≈ max latency (since requests ran concurrently)
            total_time = stats.get('max_latency', stats['mean_latency'])
        else:
            # Fallback: estimate from throughput
            if 'requests_per_second' in stats and stats['requests_per_second'] > 0:
                total_time = stats.get('num_requests', 100) / stats['requests_per_second']
            else:
                total_time = stats.get('num_requests', 100) * stats.get('mean_latency', 1)

        # Calculate throughput if not provided
        if 'requests_per_second' not in stats:
            stats['requests_per_second'] = stats.get('num_requests', 100) / total_time

        # Build dashboard-compatible result
        result = {
            "model": full_model_name,
            "base_url": service_map[full_model_name],
            "total_requests": stats.get('num_requests', 100),
            "successful_requests": stats.get('num_requests', 100),
            "failed_requests": 0,
            "total_time": round(total_time, 2),
            "requests_per_second": round(stats['requests_per_second'], 2),
            "latency": {
                "mean": round(stats.get('mean_latency', 0), 3),
                "median": round(stats.get('median_latency', 0), 3),
                "min": round(stats.get('min_latency', 0), 3),
                "max": round(stats.get('max_latency', 0), 3),
                "p95": round(stats.get('p95_latency', 0), 3),
                "p99": round(stats.get('p99_latency', 0), 3)
            },
            "tokens": {
                "total": int(stats.get('total_tokens', 0)),
                "mean": round(stats.get('mean_tokens', 0), 1)
            },
            "throughput_tokens_per_sec": {
                "mean": round(stats.get('mean_tokens', 0) / stats.get('mean_latency', 1), 2) if stats.get('mean_latency', 0) > 0 else 0,
                "total": round(stats.get('total_tokens', 0) / total_time, 2) if total_time > 0 else 0
            }
        }

        all_results.append(result)

        print(f"  ✓ Converted results:")
        print(f"    - Requests/sec: {result['requests_per_second']}")
        print(f"    - Mean latency: {result['latency']['mean']}s")
        print(f"    - Tokens/sec: {result['throughput_tokens_per_sec']['total']}")

    return all_results

def main():
    parser = argparse.ArgumentParser(description="Convert GenAI-Perf results to dashboard format")
    parser.add_argument("genai_perf_dir", help="Directory containing GenAI-Perf results")
    parser.add_argument("--namespace", default="baseline", help="K8s namespace (baseline or managed)")
    parser.add_argument("--output", help="Output JSON file (default: results/<namespace>/k8s/genai-perf-results.json)")

    args = parser.parse_args()

    # Convert results
    results = convert_results(args.genai_perf_dir, args.namespace)

    if not results:
        print("\n❌ No results converted!")
        return 1

    # Determine output path
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path(__file__).parent.parent / "results" / args.namespace / "k8s" / "genai-perf-results.json"

    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Conversion complete!")
    print(f"{'='*60}")
    print(f"Converted {len(results)} model results")
    print(f"Output: {output_file}")
    print(f"\nYou can now view these results in the dashboard.")
    print(f"The dashboard will automatically load results from:")
    print(f"  - results/{args.namespace}/k8s/all-models-results.json (custom benchmark)")
    print(f"  - results/{args.namespace}/k8s/genai-perf-results.json (GenAI-Perf)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
