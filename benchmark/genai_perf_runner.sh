#!/bin/bash
set -e

# GenAI-Perf Benchmark Runner
# Usage: ./genai_perf_runner.sh [baseline|managed] [model_name] [concurrency] [request_count]

ENV=$1
MODEL=${2:-"meta-llama/Llama-3.1-8B-Instruct"}
CONCURRENCY=${3:-10}
REQUEST_COUNT=${4:-100}

if [ -z "$ENV" ]; then
    echo "Usage: ./genai_perf_runner.sh [baseline|managed] [model_name] [concurrency] [request_count]"
    echo ""
    echo "Models:"
    echo "  - meta-llama/Llama-3.1-8B-Instruct"
    echo "  - Qwen/Qwen2.5-7B-Instruct"
    echo "  - meta-llama/Llama-3.3-70B-Instruct"
    exit 1
fi

if [ "$ENV" != "baseline" ] && [ "$ENV" != "managed" ]; then
    echo "Error: Environment must be 'baseline' or 'managed'"
    exit 1
fi

# Set endpoint URL based on environment
if [ "$ENV" = "baseline" ]; then
    URL="http://localhost:8080"
else
    URL="http://localhost:8081"
fi

# Create output directory
OUTPUT_DIR="results/$ENV/genai_perf_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "===================================="
echo "GenAI-Perf Benchmark"
echo "===================================="
echo "Environment: $ENV"
echo "Model: $MODEL"
echo "URL: $URL"
echo "Concurrency: $CONCURRENCY"
echo "Request Count: $REQUEST_COUNT"
echo "Output: $OUTPUT_DIR"
echo "===================================="
echo ""

# Check if genai-perf is installed
if ! command -v genai-perf &> /dev/null; then
    echo "genai-perf not found. Installing..."
    pip3 install genai-perf
fi

# Run genai-perf benchmark
genai-perf profile \
  -m "$MODEL" \
  --backend vllm \
  --url "$URL" \
  --streaming \
  --concurrency "$CONCURRENCY" \
  --request-count "$REQUEST_COUNT" \
  --synthetic-input-tokens-mean 512 \
  --synthetic-input-tokens-stddev 128 \
  --output-tokens-mean 256 \
  --output-tokens-stddev 64 \
  --generate-plots

# Move results to output directory
if [ -d "artifacts" ]; then
    mv artifacts/* "$OUTPUT_DIR/" || true
    rmdir artifacts || true
fi

echo ""
echo "===================================="
echo "Benchmark complete!"
echo "Results saved to: $OUTPUT_DIR"
echo "===================================="
