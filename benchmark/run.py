#!/usr/bin/env python3
"""
ModelsGuard Benchmark Runner

Benchmarks vLLM inference performance across baseline and managed environments.
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Dict
import sys

from clients.vllm_client import VLLMBenchmarkClient
from workloads.workload_generator import WorkloadGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(
        self,
        endpoint: str,
        workload_config: Dict,
        output_dir: Path,
        num_requests: int = 100,
        concurrency: int = 10
    ):
        self.endpoint = endpoint
        self.workload_config = workload_config
        self.output_dir = output_dir
        self.num_requests = num_requests
        self.concurrency = concurrency
        self.client = VLLMBenchmarkClient(endpoint)

    async def run(self) -> Dict:
        """Run the benchmark and return results."""
        logger.info(f"Starting benchmark against {self.endpoint}")
        logger.info(f"Requests: {self.num_requests}, Concurrency: {self.concurrency}")

        # Generate workload
        workload_gen = WorkloadGenerator(self.workload_config)
        requests = workload_gen.generate(self.num_requests)

        # Run benchmark
        start_time = time.time()
        results = await self.client.run_benchmark(
            requests=requests,
            concurrency=self.concurrency
        )
        total_time = time.time() - start_time

        # Calculate metrics
        metrics = self._calculate_metrics(results, total_time)

        # Save results
        self._save_results(results, metrics)

        return metrics

    def _calculate_metrics(self, results: List[Dict], total_time: float) -> Dict:
        """Calculate benchmark metrics."""
        ttfts = [r['ttft'] for r in results if r.get('ttft')]
        latencies = [r['latency'] for r in results if r.get('latency')]
        throughputs = [r['throughput'] for r in results if r.get('throughput')]
        errors = [r for r in results if r.get('error')]

        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            k = (len(sorted_data) - 1) * p
            f = int(k)
            c = f + 1 if f < len(sorted_data) - 1 else f
            return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

        metrics = {
            'total_requests': len(results),
            'successful_requests': len(results) - len(errors),
            'failed_requests': len(errors),
            'total_time': total_time,
            'requests_per_sec': len(results) / total_time if total_time > 0 else 0,
            'ttft': {
                'p50': percentile(ttfts, 0.5),
                'p90': percentile(ttfts, 0.9),
                'p99': percentile(ttfts, 0.99),
                'mean': sum(ttfts) / len(ttfts) if ttfts else 0,
            },
            'latency': {
                'p50': percentile(latencies, 0.5),
                'p90': percentile(latencies, 0.9),
                'p99': percentile(latencies, 0.99),
                'mean': sum(latencies) / len(latencies) if latencies else 0,
            },
            'throughput': {
                'mean': sum(throughputs) / len(throughputs) if throughputs else 0,
                'total_tokens': sum(r.get('total_tokens', 0) for r in results),
                'tokens_per_sec': sum(r.get('total_tokens', 0) for r in results) / total_time if total_time > 0 else 0,
            }
        }

        return metrics

    def _save_results(self, results: List[Dict], metrics: Dict):
        """Save benchmark results to files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save detailed results
        results_file = self.output_dir / f"results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved detailed results to {results_file}")

        # Save metrics summary
        metrics_file = self.output_dir / f"metrics_{int(time.time())}.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved metrics to {metrics_file}")

        # Print summary
        self._print_summary(metrics)

    def _print_summary(self, metrics: Dict):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        print(f"Total Requests: {metrics['total_requests']}")
        print(f"Successful: {metrics['successful_requests']}")
        print(f"Failed: {metrics['failed_requests']}")
        print(f"Total Time: {metrics['total_time']:.2f}s")
        print(f"Requests/sec: {metrics['requests_per_sec']:.2f}")
        print(f"Tokens/sec: {metrics['throughput']['tokens_per_sec']:.2f}")
        print("\nTime to First Token (TTFT):")
        print(f"  P50: {metrics['ttft']['p50']:.3f}s")
        print(f"  P90: {metrics['ttft']['p90']:.3f}s")
        print(f"  P99: {metrics['ttft']['p99']:.3f}s")
        print(f"  Mean: {metrics['ttft']['mean']:.3f}s")
        print("\nEnd-to-End Latency:")
        print(f"  P50: {metrics['latency']['p50']:.3f}s")
        print(f"  P90: {metrics['latency']['p90']:.3f}s")
        print(f"  P99: {metrics['latency']['p99']:.3f}s")
        print(f"  Mean: {metrics['latency']['mean']:.3f}s")
        print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description='Run ModelsGuard benchmark')
    parser.add_argument(
        '--env',
        choices=['baseline', 'managed'],
        required=True,
        help='Environment to benchmark (baseline or managed)'
    )
    parser.add_argument(
        '--endpoint',
        help='Custom endpoint URL (default: http://localhost:8080 for baseline, 8081 for managed)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output directory for results'
    )
    parser.add_argument(
        '--num-requests',
        type=int,
        default=100,
        help='Number of requests to send (default: 100)'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=10,
        help='Number of concurrent requests (default: 10)'
    )
    parser.add_argument(
        '--workload',
        type=Path,
        default=Path('benchmark/workloads/default.json'),
        help='Path to workload configuration file'
    )

    args = parser.parse_args()

    # Set default endpoint based on environment
    if args.endpoint:
        endpoint = args.endpoint
    else:
        endpoint = "http://localhost:8080" if args.env == "baseline" else "http://localhost:8081"

    # Set output directory
    output_dir = args.output or Path(f"results/{args.env}")

    # Load workload config
    try:
        with open(args.workload) as f:
            workload_config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Workload configuration file not found: {args.workload}")
        sys.exit(1)

    # Run benchmark
    runner = BenchmarkRunner(
        endpoint=endpoint,
        workload_config=workload_config,
        output_dir=output_dir,
        num_requests=args.num_requests,
        concurrency=args.concurrency
    )

    try:
        await runner.run()
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
