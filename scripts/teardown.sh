#!/bin/bash
set -e

# ModelsGuard Teardown Script
# Usage: ./scripts/teardown.sh [baseline|managed|all]

ENV=$1

if [ -z "$ENV" ]; then
    echo "Usage: ./scripts/teardown.sh [baseline|managed|all]"
    exit 1
fi

teardown_env() {
    local env=$1
    echo "===================================="
    echo "Tearing down $env environment"
    echo "===================================="

    if [ -d "docker/$env" ]; then
        cd "docker/$env"
        docker-compose down -v
        cd ../..
        echo "✓ $env environment stopped and removed"
    else
        echo "✗ docker/$env directory not found"
    fi
}

if [ "$ENV" = "all" ]; then
    teardown_env "baseline"
    teardown_env "managed"
elif [ "$ENV" = "baseline" ] || [ "$ENV" = "managed" ]; then
    teardown_env "$ENV"
else
    echo "Error: Environment must be 'baseline', 'managed', or 'all'"
    exit 1
fi

echo ""
echo "===================================="
echo "Teardown complete!"
echo "===================================="
