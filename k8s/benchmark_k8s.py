#!/usr/bin/env python3
import time
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

def benchmark_model(base_url, model_name, num_requests=100, concurrency=10):
    """Benchmark a model endpoint"""
    client = OpenAI(
        base_url=base_url,
        api_key="dummy"
    )
    
    prompt = "Write a short story about a robot learning to paint."
    
    def send_request(request_id):
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7
            )
            latency = time.time() - start
            tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
            return {
                "request_id": request_id,
                "latency": latency,
                "tokens": tokens,
                "throughput": tokens / latency if latency > 0 else 0,
                "success": True
            }
        except Exception as e:
            return {
                "request_id": request_id,
                "latency": time.time() - start,
                "error": str(e),
                "success": False
            }
    
    print(f"\n{'='*60}")
    print(f"Benchmarking {model_name}")
    print(f"URL: {base_url}")
    print(f"Requests: {num_requests}, Concurrency: {concurrency}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, i) for i in range(num_requests)]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            if i % 10 == 0:
                print(f"Completed {i}/{num_requests} requests...")
    
    total_time = time.time() - start_time
    
    # Calculate metrics
    successful = [r for r in results if r["success"]]
    failed = len(results) - len(successful)
    
    if successful:
        latencies = [r["latency"] for r in successful]
        tokens = [r["tokens"] for r in successful]
        throughputs = [r["throughput"] for r in successful]
        
        metrics = {
            "model": model_name,
            "base_url": base_url,
            "total_requests": num_requests,
            "successful_requests": len(successful),
            "failed_requests": failed,
            "total_time": total_time,
            "requests_per_second": len(successful) / total_time,
            "latency": {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
                "p99": sorted(latencies)[int(len(latencies) * 0.99)],
            },
            "tokens": {
                "total": sum(tokens),
                "mean": statistics.mean(tokens) if tokens else 0,
            },
            "throughput_tokens_per_sec": {
                "mean": statistics.mean(throughputs) if throughputs else 0,
                "total": sum(tokens) / total_time if total_time > 0 else 0,
            }
        }
        
        print(f"\n{'='*60}")
        print(f"Results for {model_name}")
        print(f"{'='*60}")
        print(f"Total Requests: {metrics['total_requests']}")
        print(f"Successful: {metrics['successful_requests']}, Failed: {metrics['failed_requests']}")
        print(f"Total Time: {metrics['total_time']:.2f}s")
        print(f"Requests/sec: {metrics['requests_per_second']:.2f}")
        print(f"\nLatency (seconds):")
        print(f"  Mean: {metrics['latency']['mean']:.3f}")
        print(f"  Median: {metrics['latency']['median']:.3f}")
        print(f"  P95: {metrics['latency']['p95']:.3f}")
        print(f"  P99: {metrics['latency']['p99']:.3f}")
        print(f"  Min: {metrics['latency']['min']:.3f}")
        print(f"  Max: {metrics['latency']['max']:.3f}")
        print(f"\nTokens:")
        print(f"  Total: {metrics['tokens']['total']}")
        print(f"  Mean per request: {metrics['tokens']['mean']:.1f}")
        print(f"\nThroughput:")
        print(f"  Tokens/sec (mean): {metrics['throughput_tokens_per_sec']['mean']:.2f}")
        print(f"  Tokens/sec (total): {metrics['throughput_tokens_per_sec']['total']:.2f}")
        print(f"{'='*60}\n")
        
        return metrics
    else:
        print(f"ERROR: All {num_requests} requests failed!")
        return None

if __name__ == "__main__":
    models = [
        {
            "name": "meta-llama/Llama-3.1-8B-Instruct",
            "url": "http://vllm-llama-8b.baseline.svc.cluster.local:8000/v1",
            "output_file": "/tmp/llama-8b-results.json"
        },
        {
            "name": "Qwen/Qwen2.5-7B-Instruct",
            "url": "http://vllm-qwen-7b.baseline.svc.cluster.local:8000/v1",
            "output_file": "/tmp/qwen-7b-results.json"
        },
        {
            "name": "mistralai/Mistral-7B-Instruct-v0.3",
            "url": "http://vllm-mistral-7b.baseline.svc.cluster.local:8000/v1",
            "output_file": "/tmp/mistral-7b-results.json"
        }
    ]
    
    all_results = []
    for model_config in models:
        metrics = benchmark_model(
            base_url=model_config["url"],
            model_name=model_config["name"],
            num_requests=100,
            concurrency=10
        )
        if metrics:
            all_results.append(metrics)
            with open(model_config["output_file"], 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"Results saved to {model_config['output_file']}\n")
    
    # Save combined results
    with open('/tmp/all-models-results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETE - All models tested")
    print("="*60)
