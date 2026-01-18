# GenAI-Perf Kubernetes Benchmarking Guide

This guide shows you how to run NVIDIA GenAI-Perf benchmarks against your Kubernetes vLLM deployments and display the results in the dashboard.

## Overview

We have 3 components:

1. **`genai_perf_k8s.sh`** - Runs GenAI-Perf against K8s services via port-forward
2. **`convert_genai_perf_results.py`** - Converts GenAI-Perf output to dashboard format
3. **Dashboard** - Displays both custom and GenAI-Perf results with comparison

## Prerequisites

- K8s cluster with vLLM pods running (baseline or managed namespace)
- `genai-perf` installed (script will auto-install if missing)
- `kubectl` access to the cluster

## Quick Start

### Step 1: SSH to Your GCP Instance

```bash
# Get the instance IP from terraform
cd terraform
INSTANCE_IP=$(terraform output -raw instance_ip)
echo $INSTANCE_IP

# SSH to the instance
ssh -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP
```

### Step 2: Upload Scripts to GCP Instance

From your local machine:

```bash
# Upload the scripts
scp -i ~/.ssh/google_compute_engine \
  k8s/genai_perf_k8s.sh \
  k8s/convert_genai_perf_results.py \
  davidengstler@$INSTANCE_IP:~/

# SSH to the instance
ssh -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP
```

### Step 3: Run GenAI-Perf Benchmarks

On the GCP instance:

```bash
# Make script executable
chmod +x genai_perf_k8s.sh

# Run benchmarks (this will take ~10-15 minutes)
./genai_perf_k8s.sh baseline 10 100

# Results will be saved to /tmp/genai_perf_k8s_<timestamp>/
```

**What the script does:**
- Installs genai-perf if not present
- Iterates through all 3 models (Llama, Qwen, Mistral)
- Uses `kubectl port-forward` to connect to each K8s service
- Runs GenAI-Perf with proper vLLM/OpenAI parameters
- Saves results to organized directories

### Step 4: Convert Results to Dashboard Format

Still on the GCP instance:

```bash
# Find your results directory
RESULTS_DIR=$(ls -td /tmp/genai_perf_k8s_* | head -1)
echo "Results directory: $RESULTS_DIR"

# Convert to dashboard format
python3 convert_genai_perf_results.py $RESULTS_DIR --namespace baseline

# This creates: ~/results/baseline/k8s/genai-perf-results.json
```

### Step 5: Download Results to Local Machine

From your local machine:

```bash
# Download the converted results
scp -i ~/.ssh/google_compute_engine \
  davidengstler@$INSTANCE_IP:~/results/baseline/k8s/genai-perf-results.json \
  results/baseline/k8s/
```

### Step 6: View in Dashboard

The dashboard will automatically detect and load GenAI-Perf results:

```bash
# Dashboard is already running at http://localhost:8501
# Open it in your browser and select "GenAI-Perf" from the dropdown
```

## Command Reference

### genai_perf_k8s.sh

```bash
./genai_perf_k8s.sh [namespace] [concurrency] [request_count]

# Examples:
./genai_perf_k8s.sh baseline 10 100      # Baseline with 10 concurrent, 100 requests
./genai_perf_k8s.sh managed 20 200       # Managed with 20 concurrent, 200 requests
```

**Parameters:**
- `namespace`: K8s namespace (`baseline` or `managed`)
- `concurrency`: Number of concurrent requests (default: 10)
- `request_count`: Total number of requests (default: 100)

### convert_genai_perf_results.py

```bash
python3 convert_genai_perf_results.py <genai_perf_dir> [--namespace baseline|managed] [--output path]

# Examples:
python3 convert_genai_perf_results.py /tmp/genai_perf_k8s_20250118_143000 --namespace baseline
python3 convert_genai_perf_results.py /tmp/genai_perf_k8s_20250118_143000 --output custom_output.json
```

## Dashboard Features

The updated dashboard now supports:

1. **Benchmark Type Selector** - Choose between:
   - Custom Benchmark (existing OpenAI client benchmark)
   - GenAI-Perf (NVIDIA official tool)
   - Both (Comparison) - Compare both benchmark methods

2. **All Existing Views** - Side-by-side, overlay, single environment

3. **Automatic Detection** - Dashboard automatically finds both result files

## File Structure

```
results/
├── baseline/
│   └── k8s/
│       ├── all-models-results.json      # Custom benchmark results
│       └── genai-perf-results.json      # GenAI-Perf results
└── managed/
    └── k8s/
        ├── all-models-results.json
        └── genai-perf-results.json
```

## Troubleshooting

### GenAI-Perf installation fails

```bash
# Manual installation
pip3 install --user genai-perf

# Or use pip instead of pip3
pip install genai-perf
```

### Port-forward fails

```bash
# Check if pods are running
sudo k3s kubectl get pods -n baseline

# Check if services exist
sudo k3s kubectl get svc -n baseline

# Manually test port-forward
sudo k3s kubectl port-forward -n baseline service/vllm-llama-8b 9000:8000
curl http://localhost:9000/health
```

### Conversion script fails

```bash
# Check GenAI-Perf output files
ls -la /tmp/genai_perf_k8s_*/*/

# Each model directory should contain:
# - profile_export.json
# - profile_export.csv
# - genai_perf.log
```

### Results not showing in dashboard

```bash
# Verify files exist locally
ls -la results/baseline/k8s/
ls -la results/managed/k8s/

# Check JSON format
cat results/baseline/k8s/genai-perf-results.json | jq .
```

## Complete Workflow Example

```bash
# 1. Local: Get instance IP
cd terraform && INSTANCE_IP=$(terraform output -raw instance_ip)

# 2. Local: Upload scripts
scp -i ~/.ssh/google_compute_engine k8s/*.{sh,py} davidengstler@$INSTANCE_IP:~/

# 3. SSH to instance
ssh -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP

# 4. On instance: Run benchmark
chmod +x genai_perf_k8s.sh
./genai_perf_k8s.sh baseline 10 100

# 5. On instance: Convert results
RESULTS_DIR=$(ls -td /tmp/genai_perf_k8s_* | head -1)
python3 convert_genai_perf_results.py $RESULTS_DIR --namespace baseline

# 6. On instance: Verify output
ls -la results/baseline/k8s/genai-perf-results.json
cat results/baseline/k8s/genai-perf-results.json | head -50

# 7. Local: Download results
scp -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP:results/baseline/k8s/genai-perf-results.json results/baseline/k8s/

# 8. Local: View dashboard
# Open http://localhost:8501 in browser
# Select "GenAI-Perf" from dropdown
```

## Comparing Custom vs GenAI-Perf Benchmarks

Once you have both benchmark results, you can compare methodologies:

1. Navigate to dashboard at http://localhost:8501
2. Select "Both (Comparison)" from Benchmark Type dropdown
3. Compare metrics between the two approaches

**Key Differences:**
- **Custom**: Simple OpenAI client, fixed prompt, basic metrics
- **GenAI-Perf**: Official NVIDIA tool, synthetic input tokens, detailed metrics, streaming support

## Notes

- GenAI-Perf benchmarks take longer (~10-15 min for all models)
- Port-forward requires sudo access to kubectl
- Each model benchmark waits 5 seconds between tests
- Results include full GenAI-Perf logs in each model directory
