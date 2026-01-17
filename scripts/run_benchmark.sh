#!/bin/bash
set -e

# ModelsGuard Benchmark Script
# Usage: ./scripts/run_benchmark.sh [baseline|managed|both] [num_requests] [concurrency]

ENV=$1
NUM_REQUESTS=${2:-100}
CONCURRENCY=${3:-10}

if [ -z "$ENV" ]; then
    echo "Usage: ./scripts/run_benchmark.sh [baseline|managed|both] [num_requests] [concurrency]"
    exit 1
fi

run_benchmark() {
    local env=$1
    echo "===================================="
    echo "Running benchmark: $env"
    echo "Requests: $NUM_REQUESTS"
    echo "Concurrency: $CONCURRENCY"
    echo "===================================="

    python3 benchmark/run.py \
        --env "$env" \
        --num-requests "$NUM_REQUESTS" \
        --concurrency "$CONCURRENCY" \
        --output "results/$env"

    echo "✓ Benchmark complete for $env"
}

# Check if benchmark dependencies are installed
if ! python3 -c "import aiohttp" 2>/dev/null; then
    echo "Installing benchmark dependencies..."
    pip3 install -r benchmark/requirements.txt
fi

if [ "$ENV" = "both" ]; then
    run_benchmark "baseline"
    echo ""
    run_benchmark "managed"
elif [ "$ENV" = "baseline" ] || [ "$ENV" = "managed" ]; then
    run_benchmark "$ENV"
else
    echo "Error: Environment must be 'baseline', 'managed', or 'both'"
    exit 1
fi

echo ""
echo "===================================="
echo "All benchmarks complete!"
echo "Results saved to: results/"
echo "===================================="
