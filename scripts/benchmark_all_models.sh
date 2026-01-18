#!/bin/bash
set -e

# Comprehensive GenAI-Perf Benchmark Script
# Runs benchmarks across all models for a given environment
# Usage: ./scripts/benchmark_all_models.sh [baseline|managed] [concurrency] [request_count]

ENV=$1
CONCURRENCY=${2:-10}
REQUEST_COUNT=${3:-100}

if [ -z "$ENV" ]; then
    echo "Usage: ./scripts/benchmark_all_models.sh [baseline|managed] [concurrency] [request_count]"
    exit 1
fi

if [ "$ENV" != "baseline" ] && [ "$ENV" != "managed" ]; then
    echo "Error: Environment must be 'baseline' or 'managed'"
    exit 1
fi

# Set endpoint URL
if [ "$ENV" = "baseline" ]; then
    URL="http://localhost:8080"
else
    URL="http://localhost:8081"
fi

echo "===================================="
echo "Benchmarking ALL models: $ENV"
echo "Concurrency: $CONCURRENCY"
echo "Request Count: $REQUEST_COUNT"
echo "===================================="
echo ""

# Check endpoint health
echo "Checking endpoint health..."
if ! curl -f -s "$URL/health" > /dev/null 2>&1; then
    echo "✗ Endpoint is not healthy: $URL"
    echo "Please ensure the $ENV environment is running"
    exit 1
fi
echo "✓ Endpoint is healthy"
echo ""

# Define models to benchmark
MODELS=(
    "meta-llama/Llama-3.1-8B-Instruct"
    "Qwen/Qwen2.5-7B-Instruct"
    "meta-llama/Llama-3.3-70B-Instruct"
)

# Benchmark each model
for MODEL in "${MODELS[@]}"; do
    echo "===================================="
    echo "Benchmarking: $MODEL"
    echo "===================================="

    ./benchmark/genai_perf_runner.sh "$ENV" "$MODEL" "$CONCURRENCY" "$REQUEST_COUNT"

    echo ""
    echo "Waiting 10 seconds before next benchmark..."
    sleep 10
    echo ""
done

echo "===================================="
echo "All benchmarks complete!"
echo "Results saved to: results/$ENV/"
echo "===================================="
