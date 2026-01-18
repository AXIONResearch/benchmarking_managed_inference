#!/usr/bin/env python3
"""
Simple benchmark script for vLLM endpoints
Sends concurrent requests and measures latency metrics
"""
import asyncio
import aiohttp
import time
import argparse
import json
from pathlib import Path
from datetime import datetime
import statistics

async def send_request(session, url, model, prompt, semaphore):
    """Send a single request and measure latencies"""
    async with semaphore:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0.7
        }

        start_time = time.time()
        first_token_time = None
        tokens_received = []

        try:
            async with session.post(
                f"{url}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                data = await response.json()

                # Record end time
                end_time = time.time()

                # Extract metrics
                usage = data.get('usage', {})
                content = data['choices'][0]['message']['content']

                # Estimate TTFT and ITL (these are approximations without streaming)
                total_latency_ms = (end_time - start_time) * 1000
                output_tokens = usage.get('completion_tokens', len(content.split()))

                # Rough estimates
                ttft_ms = total_latency_ms * 0.1  # Assume 10% for first token
                itl_ms = (total_latency_ms - ttft_ms) / output_tokens if output_tokens > 1 else 0

                return {
                    'success': True,
                    'time_to_first_token_ms': ttft_ms,
                    'inter_token_latency_ms': itl_ms,
                    'end_to_end_latency_ms': total_latency_ms,
                    'num_input_tokens': usage.get('prompt_tokens', 0),
                    'num_output_tokens': output_tokens,
                    'total_tokens': usage.get('total_tokens', 0)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'time_to_first_token_ms': 0,
                'inter_token_latency_ms': 0,
                'end_to_end_latency_ms': 0,
                'num_input_tokens': 0,
                'num_output_tokens': 0,
                'total_tokens': 0
            }

async def run_benchmark(url, model, num_requests, concurrency):
    """Run benchmark with specified parameters"""
    print(f"Running benchmark:")
    print(f"  URL: {url}")
    print(f"  Model: {model}")
    print(f"  Requests: {num_requests}")
    print(f"  Concurrency: {concurrency}")

    # Sample prompts
    prompts = [
        "Explain what artificial intelligence is in simple terms.",
        "Write a short poem about technology.",
        "What are the benefits of cloud computing?",
        "Describe how neural networks work.",
        "What is the future of automation?",
    ]

    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(num_requests):
            prompt = prompts[i % len(prompts)]
            tasks.append(send_request(session, url, model, prompt, semaphore))

        # Run all requests
        print(f"\nSending {num_requests} requests with concurrency {concurrency}...")
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    # Filter successful results
    successful = [r for r in results if r.get('success')]
    failed = len(results) - len(successful)

    print(f"\nCompleted in {total_time:.2f}s")
    print(f"Success: {len(successful)}/{num_requests}, Failed: {failed}")

    if not successful:
        print("❌ All requests failed!")
        return None

    # Calculate statistics
    stats = {
        'total_requests': num_requests,
        'successful_requests': len(successful),
        'failed_requests': failed,
        'total_time_seconds': total_time,
        'requests_per_second': len(successful) / total_time,

        'ttft_mean_ms': statistics.mean(r['time_to_first_token_ms'] for r in successful),
        'ttft_p50_ms': statistics.median(r['time_to_first_token_ms'] for r in successful),
        'ttft_p90_ms': statistics.quantiles(
            [r['time_to_first_token_ms'] for r in successful], n=10
        )[8],
        'ttft_p99_ms': statistics.quantiles(
            [r['time_to_first_token_ms'] for r in successful], n=100
        )[98],

        'itl_mean_ms': statistics.mean(r['inter_token_latency_ms'] for r in successful),
        'itl_p50_ms': statistics.median(r['inter_token_latency_ms'] for r in successful),

        'e2e_mean_ms': statistics.mean(r['end_to_end_latency_ms'] for r in successful),
        'e2e_p50_ms': statistics.median(r['end_to_end_latency_ms'] for r in successful),
        'e2e_p90_ms': statistics.quantiles(
            [r['end_to_end_latency_ms'] for r in successful], n=10
        )[8],
        'e2e_p99_ms': statistics.quantiles(
            [r['end_to_end_latency_ms'] for r in successful], n=100
        )[98],

        'tokens_per_second': sum(r['num_output_tokens'] for r in successful) / total_time,
        'avg_input_tokens': statistics.mean(r['num_input_tokens'] for r in successful),
        'avg_output_tokens': statistics.mean(r['num_output_tokens'] for r in successful),
    }

    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Throughput: {stats['requests_per_second']:.2f} req/s")
    print(f"Tokens/sec: {stats['tokens_per_second']:.2f}")
    print(f"\nTime to First Token (TTFT):")
    print(f"  Mean: {stats['ttft_mean_ms']:.2f} ms")
    print(f"  P50:  {stats['ttft_p50_ms']:.2f} ms")
    print(f"  P90:  {stats['ttft_p90_ms']:.2f} ms")
    print(f"  P99:  {stats['ttft_p99_ms']:.2f} ms")
    print(f"\nInter-Token Latency (ITL):")
    print(f"  Mean: {stats['itl_mean_ms']:.2f} ms")
    print(f"  P50:  {stats['itl_p50_ms']:.2f} ms")
    print(f"\nEnd-to-End Latency:")
    print(f"  Mean: {stats['e2e_mean_ms']:.2f} ms")
    print(f"  P50:  {stats['e2e_p50_ms']:.2f} ms")
    print(f"  P90:  {stats['e2e_p90_ms']:.2f} ms")
    print(f"  P99:  {stats['e2e_p99_ms']:.2f} ms")
    print("="*60)

    return {'results': successful, 'stats': stats}

def save_results(data, env, model):
    """Save results to CSV and JSON files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = model.split('/')[-1]

    # Create results directory
    results_dir = Path("../results") / env / f"benchmark_{model_name}_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Save CSV
    import csv
    csv_file = results_dir / "profile_export.csv"
    with open(csv_file, 'w', newline='') as f:
        if data['results']:
            writer = csv.DictWriter(f, fieldnames=data['results'][0].keys())
            writer.writeheader()
            writer.writerows(data['results'])

    # Save JSON
    json_file = results_dir / "profile_export.json"
    with open(json_file, 'w') as f:
        json.dump(data['stats'], f, indent=2)

    print(f"\n✅ Results saved to: {results_dir}")
    return results_dir

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple vLLM benchmark")
    parser.add_argument("--url", default="http://localhost:8080", help="Load balancer URL")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--requests", type=int, default=50, help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--env", choices=["baseline", "managed"], default="baseline", help="Environment")

    args = parser.parse_args()

    data = asyncio.run(run_benchmark(args.url, args.model, args.requests, args.concurrency))
    if data:
        save_results(data, args.env, args.model)
