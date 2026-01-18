#!/bin/bash
set -e

# GenAI-Perf Benchmark Runner for Kubernetes
# Runs GenAI-Perf against K8s services using port-forward
# Usage: ./genai_perf_k8s.sh [baseline|managed] [concurrency] [request_count]

NAMESPACE=${1:-"baseline"}
CONCURRENCY=${2:-10}
REQUEST_COUNT=${3:-100}

# Port to use for port-forwarding
LOCAL_PORT=9000

echo "===================================="
echo "GenAI-Perf K8s Benchmark"
echo "===================================="
echo "Namespace: $NAMESPACE"
echo "Concurrency: $CONCURRENCY"
echo "Request Count: $REQUEST_COUNT"
echo "===================================="
echo ""

# Check if genai-perf is installed
if ! command -v genai-perf &> /dev/null; then
    echo "genai-perf not found. Installing..."

    # Try different pip commands
    if command -v pip3 &> /dev/null; then
        pip3 install --user genai-perf
    elif command -v pip &> /dev/null; then
        pip install --user genai-perf
    elif command -v python3 &> /dev/null; then
        python3 -m pip install --user genai-perf
    else
        echo "ERROR: No pip installation found. Please install pip first:"
        echo "  sudo apt-get update && sudo apt-get install -y python3-pip"
        exit 1
    fi

    # Add user bin to PATH if needed
    export PATH="$HOME/.local/bin:$PATH"
fi

# Define models and their services
declare -A MODELS=(
    ["meta-llama/Llama-3.1-8B-Instruct"]="vllm-llama-8b"
    ["Qwen/Qwen2.5-7B-Instruct"]="vllm-qwen-7b"
    ["mistralai/Mistral-7B-Instruct-v0.3"]="vllm-mistral-7b"
)

# Create output directory
OUTPUT_DIR="/tmp/genai_perf_k8s_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# Function to run benchmark for a model
benchmark_model() {
    local MODEL=$1
    local SERVICE=$2
    local MODEL_SHORT=$(echo "$MODEL" | cut -d'/' -f2)

    echo ""
    echo "===================================="
    echo "Benchmarking: $MODEL"
    echo "Service: $SERVICE"
    echo "===================================="

    # Start port-forward in background
    echo "Starting port-forward to $SERVICE..."
    sudo k3s kubectl port-forward -n "$NAMESPACE" "service/$SERVICE" "$LOCAL_PORT:8000" > /dev/null 2>&1 &
    PF_PID=$!

    # Wait for port-forward to be ready
    sleep 3

    # Test connectivity
    if ! curl -s "http://localhost:$LOCAL_PORT/health" > /dev/null; then
        echo "ERROR: Cannot connect to service $SERVICE"
        kill $PF_PID 2>/dev/null || true
        return 1
    fi

    echo "✓ Connected to $SERVICE"

    # Create model-specific output directory
    MODEL_OUTPUT="$OUTPUT_DIR/$MODEL_SHORT"
    mkdir -p "$MODEL_OUTPUT"

    # Run genai-perf
    cd "$MODEL_OUTPUT"
    genai-perf profile \
      -m "$MODEL" \
      --service-kind openai \
      --endpoint v1/chat/completions \
      --endpoint-type chat \
      --url "http://localhost:$LOCAL_PORT" \
      --streaming \
      --concurrency "$CONCURRENCY" \
      --num-prompts "$REQUEST_COUNT" \
      --random-seed 123 \
      --synthetic-input-tokens-mean 100 \
      --synthetic-input-tokens-stddev 20 \
      --tokenizer "$MODEL" \
      2>&1 | tee genai_perf.log

    # Kill port-forward
    kill $PF_PID 2>/dev/null || true
    wait $PF_PID 2>/dev/null || true

    echo "✓ Benchmark complete for $MODEL"
    echo "Results saved to: $MODEL_OUTPUT"

    # Wait between benchmarks
    sleep 5
}

# Run benchmarks for all models
for MODEL in "${!MODELS[@]}"; do
    SERVICE="${MODELS[$MODEL]}"
    benchmark_model "$MODEL" "$SERVICE" || echo "⚠ Benchmark failed for $MODEL"
done

echo ""
echo "===================================="
echo "All benchmarks complete!"
echo "Results directory: $OUTPUT_DIR"
echo "===================================="
echo ""
echo "To convert results to dashboard format, run:"
echo "python3 k8s/convert_genai_perf_results.py $OUTPUT_DIR"
