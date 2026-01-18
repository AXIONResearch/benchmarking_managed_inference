#!/bin/bash
set -e

# Complete End-to-End GenAI-Perf Benchmark Script for Baseline K8s
# This script:
# 1. Uploads benchmark scripts to GCP instance
# 2. Runs GenAI-Perf benchmarks on all models
# 3. Converts results to dashboard format
# 4. Downloads results to local machine
# 5. Opens dashboard to view results

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
INSTANCE_IP="34.169.140.201"
SSH_KEY="$HOME/.ssh/google_compute_engine"
SSH_USER="davidengstler"
NAMESPACE="baseline"
CONCURRENCY=${1:-10}
REQUEST_COUNT=${2:-100}

echo "===================================="
echo "GenAI-Perf Baseline Benchmark"
echo "===================================="
echo "Instance: $INSTANCE_IP"
echo "Namespace: $NAMESPACE"
echo "Concurrency: $CONCURRENCY"
echo "Request Count: $REQUEST_COUNT"
echo "===================================="
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY"
    exit 1
fi

# Check if scripts exist
if [ ! -f "$PROJECT_ROOT/k8s/genai_perf_k8s.sh" ]; then
    echo "ERROR: genai_perf_k8s.sh not found"
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/k8s/convert_genai_perf_results.py" ]; then
    echo "ERROR: convert_genai_perf_results.py not found"
    exit 1
fi

echo "Step 1: Uploading scripts to GCP instance..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/k8s/genai_perf_k8s.sh" \
    "$PROJECT_ROOT/k8s/convert_genai_perf_results.py" \
    "$SSH_USER@$INSTANCE_IP:~/"

echo "✓ Scripts uploaded"
echo ""

echo "Step 2: Running GenAI-Perf benchmarks (this will take ~10-15 minutes)..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$INSTANCE_IP" << 'ENDSSH'
set -e

# Make script executable
chmod +x genai_perf_k8s.sh

# Run the benchmark
./genai_perf_k8s.sh baseline 10 100

# Find the results directory
RESULTS_DIR=$(ls -td /tmp/genai_perf_k8s_* | head -1)
echo ""
echo "Results directory: $RESULTS_DIR"
echo ""

# Create results directory structure
mkdir -p results/baseline/k8s

# Convert results to dashboard format
echo "Converting results to dashboard format..."
python3 convert_genai_perf_results.py "$RESULTS_DIR" --namespace baseline

# Verify output
if [ -f "results/baseline/k8s/genai-perf-results.json" ]; then
    echo "✓ Conversion complete"
    echo ""
    echo "Results preview:"
    head -50 results/baseline/k8s/genai-perf-results.json
else
    echo "ERROR: Conversion failed"
    exit 1
fi
ENDSSH

if [ $? -ne 0 ]; then
    echo "ERROR: Benchmark or conversion failed"
    exit 1
fi

echo ""
echo "Step 3: Downloading results to local machine..."

# Create local results directory
mkdir -p "$PROJECT_ROOT/results/baseline/k8s"

# Download results
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    "$SSH_USER@$INSTANCE_IP:results/baseline/k8s/genai-perf-results.json" \
    "$PROJECT_ROOT/results/baseline/k8s/"

echo "✓ Results downloaded to: results/baseline/k8s/genai-perf-results.json"
echo ""

echo "===================================="
echo "✅ BENCHMARK COMPLETE!"
echo "===================================="
echo ""
echo "Results summary:"
cat "$PROJECT_ROOT/results/baseline/k8s/genai-perf-results.json" | python3 -m json.tool | grep -A 2 '"model":\|"requests_per_second":\|"mean":'
echo ""
echo "===================================="
echo "Next steps:"
echo "===================================="
echo "1. Open dashboard: http://localhost:8501"
echo "2. Select 'GenAI-Perf' from Benchmark Type dropdown"
echo "3. View results in any of the three view modes"
echo ""
echo "To view the dashboard now, run:"
echo "  cd dashboard && streamlit run comparative_dashboard.py"
echo ""
