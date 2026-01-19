#!/bin/bash
set -e

# Simple benchmark script that uses kubectl port-forward
# This script benchmarks one model at a time using port-forward

NAMESPACE="baseline"
LOCAL_PORT=9000

echo "===================================="
echo "K8s Benchmark with Port-Forward"
echo "===================================="
echo ""

# Models and their services
declare -A MODELS=(
    ["meta-llama/Llama-3.1-8B-Instruct"]="vllm-llama-8b"
    ["Qwen/Qwen2.5-7B-Instruct"]="vllm-qwen-7b"
    ["mistralai/Mistral-7B-Instruct-v0.3"]="vllm-mistral-7b"
)

# Temporary Python script for benchmarking a single model
cat > /tmp/benchmark_single.py << 'EOPY'
import sys
import time
import json
from openai import OpenAI

def benchmark(url, model_name, num_requests=20):
    client = OpenAI(base_url=url, api_key="dummy")
    prompt = "Write a short story about a robot learning to paint."

    print(f"Benchmarking {model_name}...")
    print(f"Sending {num_requests} requests...")

    results = []
    for i in range(num_requests):
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.7
            )
            latency = time.time() - start
            tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
            results.append({"latency": latency, "tokens": tokens, "success": True})
            print(f"  Request {i+1}/{num_requests}: {latency:.2f}s, {tokens} tokens")
        except Exception as e:
            results.append({"latency": time.time() - start, "success": False, "error": str(e)})
            print(f"  Request {i+1}/{num_requests}: FAILED - {e}")

    # Calculate metrics
    successful = [r for r in results if r["success"]]
    if successful:
        avg_latency = sum(r["latency"] for r in successful) / len(successful)
        avg_tokens = sum(r["tokens"] for r in successful) / len(successful)
        total_tokens = sum(r["tokens"] for r in successful)
        total_time = sum(r["latency"] for r in successful)

        print(f"\n✓ Results:")
        print(f"  Success Rate: {len(successful)}/{num_requests}")
        print(f"  Avg Latency: {avg_latency:.3f}s")
        print(f"  Avg Tokens: {avg_tokens:.1f}")
        print(f"  Throughput: {total_tokens/total_time:.2f} tokens/sec")
        return {
            "model": model_name,
            "successful_requests": len(successful),
            "total_requests": num_requests,
            "avg_latency": avg_latency,
            "avg_tokens": avg_tokens,
            "throughput": total_tokens/total_time
        }
    else:
        print(f"\n✗ All requests failed!")
        return None

if __name__ == "__main__":
    url = sys.argv[1]
    model = sys.argv[2]
    result = benchmark(url, model)
    if result:
        with open(f"/tmp/{model.split('/')[-1]}-results.json", "w") as f:
            json.dump(result, f, indent=2)
EOPY

all_results=()

# Benchmark each model
for MODEL in "${!MODELS[@]}"; do
    SERVICE="${MODELS[$MODEL]}"
    echo ""
    echo "===================================="
    echo "Model: $MODEL"
    echo "Service: $SERVICE"
    echo "===================================="

    # Start port-forward in background
    echo "Starting port-forward..."
    sudo k3s kubectl port-forward -n "$NAMESPACE" "service/$SERVICE" "$LOCAL_PORT:8000" > /dev/null 2>&1 &
    PF_PID=$!

    # Give port-forward a moment to establish
    sleep 2

    # Wait for port-forward to be ready with retry logic
    echo "Waiting for port-forward and model to be ready..."
    MAX_RETRIES=15
    RETRY_COUNT=0
    MODEL_READY=false

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        sleep 1

        # Check if model is loaded by querying /v1/models
        RESPONSE=$(curl -s "http://localhost:$LOCAL_PORT/v1/models" 2>/dev/null || echo "")

        # Debug: show what we got (only on first few tries)
        if [ $RETRY_COUNT -lt 3 ]; then
            echo "  [Debug attempt $((RETRY_COUNT+1))]: Response length: ${#RESPONSE}"
        fi

        # Check if model name appears in response
        if echo "$RESPONSE" | grep -q "$MODEL"; then
            echo "✓ Model $MODEL is ready on $SERVICE"
            MODEL_READY=true
            break
        fi

        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $((RETRY_COUNT % 5)) -eq 0 ]; then
            echo "  Still waiting... ($RETRY_COUNT/$MAX_RETRIES)"
        fi
    done

    # Test connectivity and model availability
    if [ "$MODEL_READY" = true ]; then

        # Run benchmark
        python3 /tmp/benchmark_single.py "http://localhost:$LOCAL_PORT/v1" "$MODEL"

    else
        echo "✗ Cannot connect to $SERVICE"
    fi

    # Kill port-forward and clean up thoroughly
    echo "Cleaning up port-forward..."
    # Kill the entire process group (sudo + kubectl)
    sudo pkill -P $PF_PID 2>/dev/null || true  # Kill children first
    kill $PF_PID 2>/dev/null || true            # Kill parent
    wait $PF_PID 2>/dev/null || true

    # Extra cleanup: kill any lingering port-forwards on this port
    sudo lsof -ti:$LOCAL_PORT | xargs -r sudo kill -9 2>/dev/null || true

    # Wait between models to ensure port is released
    sleep 2
    echo ""
done

echo ""
echo "===================================="
echo "✓ Benchmark Complete!"
echo "===================================="
echo ""
echo "Results saved in /tmp/*-results.json"
