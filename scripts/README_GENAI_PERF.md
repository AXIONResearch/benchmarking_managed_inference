# GenAI-Perf Benchmark Automation Script

## One-Command Solution

Run GenAI-Perf benchmarks against your baseline K8s deployment with a single command!

## Usage

```bash
# From project root
./scripts/run_genai_perf_baseline.sh [concurrency] [request_count]

# Examples:
./scripts/run_genai_perf_baseline.sh           # Use defaults (10 concurrent, 100 requests)
./scripts/run_genai_perf_baseline.sh 20 200    # 20 concurrent, 200 requests
```

## What This Script Does

The script fully automates the entire GenAI-Perf benchmark workflow:

1. ✅ **Uploads Scripts** - Transfers benchmark scripts to GCP instance
2. ✅ **Runs Benchmarks** - Executes GenAI-Perf against all 3 models:
   - Llama-3.1-8B-Instruct
   - Qwen2.5-7B-Instruct
   - Mistral-7B-Instruct-v0.3
3. ✅ **Converts Results** - Transforms GenAI-Perf output to dashboard format
4. ✅ **Downloads Results** - Retrieves results to local `results/baseline/k8s/`
5. ✅ **Shows Summary** - Displays quick results preview

## Time Estimate

- **Total Duration**: ~10-15 minutes
- **Per Model**: ~3-5 minutes
- **Breakdown**:
  - Upload: <10 seconds
  - GenAI-Perf install (first time): ~1 minute
  - Benchmarking: ~9-12 minutes
  - Conversion: <5 seconds
  - Download: <5 seconds

## Prerequisites

✅ SSH key at `~/.ssh/google_compute_engine`
✅ GCP instance running at `34.169.140.201`
✅ K8s baseline pods running and healthy

## Output

### During Execution

```
====================================
GenAI-Perf Baseline Benchmark
====================================
Instance: 34.169.140.201
Namespace: baseline
Concurrency: 10
Request Count: 100
====================================

Step 1: Uploading scripts to GCP instance...
✓ Scripts uploaded

Step 2: Running GenAI-Perf benchmarks (this will take ~10-15 minutes)...

====================================
Benchmarking: meta-llama/Llama-3.1-8B-Instruct
Service: vllm-llama-8b
====================================
Starting port-forward to vllm-llama-8b...
✓ Connected to vllm-llama-8b
[GenAI-Perf output...]
✓ Benchmark complete for meta-llama/Llama-3.1-8B-Instruct

[... similar output for Qwen and Mistral ...]

Step 3: Downloading results to local machine...
✓ Results downloaded to: results/baseline/k8s/genai-perf-results.json

====================================
✅ BENCHMARK COMPLETE!
====================================

Results summary:
  "model": "meta-llama/Llama-3.1-8B-Instruct",
  "requests_per_second": 1.85,
      "mean": 5.21,
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "requests_per_second": 1.92,
      "mean": 5.08,
  "model": "mistralai/Mistral-7B-Instruct-v0.3",
  "requests_per_second": 2.01,
      "mean": 4.85,
```

### Files Created

```
results/baseline/k8s/genai-perf-results.json  ← Ready for dashboard!
```

## View Results

After the script completes:

```bash
# Open dashboard (if not already running)
cd dashboard
streamlit run comparative_dashboard.py

# Or open existing: http://localhost:8501
```

**In the dashboard:**
1. Select **"GenAI-Perf"** from the "Benchmark Type" dropdown
2. Choose your preferred view mode:
   - Single Environment
   - Side-by-Side Comparison (if you also have managed results)
   - Overlay Comparison

## Troubleshooting

### Script fails immediately

```bash
# Check SSH connection
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201

# Check if pods are running
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201 \
  'sudo k3s kubectl get pods -n baseline'
```

### GenAI-Perf installation fails

The script will auto-install `genai-perf`, but if it fails:

```bash
# SSH to instance and manually install
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201
pip3 install --user genai-perf
```

### Port-forward errors

If you see port-forward connection errors, pods may not be ready:

```bash
# Check pod health
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201 \
  'sudo k3s kubectl get pods -n baseline -o wide'

# Check pod logs
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201 \
  'sudo k3s kubectl logs -n baseline vllm-llama-8b-0'
```

### Results not appearing in dashboard

```bash
# Verify file exists locally
ls -la results/baseline/k8s/genai-perf-results.json

# Verify JSON is valid
cat results/baseline/k8s/genai-perf-results.json | python3 -m json.tool

# Refresh dashboard (Ctrl+R in browser)
```

## Manual Steps (If Needed)

If you prefer to run steps manually:

```bash
# 1. Upload
scp -i ~/.ssh/google_compute_engine \
  k8s/genai_perf_k8s.sh \
  k8s/convert_genai_perf_results.py \
  davidengstler@34.169.140.201:~/

# 2. SSH and run
ssh -i ~/.ssh/google_compute_engine davidengstler@34.169.140.201
chmod +x genai_perf_k8s.sh
./genai_perf_k8s.sh baseline 10 100

# 3. Convert
RESULTS_DIR=$(ls -td /tmp/genai_perf_k8s_* | head -1)
python3 convert_genai_perf_results.py $RESULTS_DIR --namespace baseline

# 4. Download (from local machine)
scp -i ~/.ssh/google_compute_engine \
  davidengstler@34.169.140.201:results/baseline/k8s/genai-perf-results.json \
  results/baseline/k8s/
```

## Comparison: Custom vs GenAI-Perf

After running both benchmarks, you can compare them:

| Metric | Custom Benchmark | GenAI-Perf |
|--------|------------------|------------|
| File | `all-models-results.json` | `genai-perf-results.json` |
| Duration | ~5 minutes | ~10-15 minutes |
| Tool | OpenAI Python SDK | NVIDIA GenAI-Perf |
| Prompts | Fixed text prompt | Synthetic tokens |
| Metrics | Basic (latency, throughput) | Advanced (TTFT, ITL) |

Use the dashboard's "Both (Comparison)" mode to see differences!

## Related Files

- **Main Script**: `scripts/run_genai_perf_baseline.sh` ← This script
- **Remote Runner**: `k8s/genai_perf_k8s.sh` (runs on GCP instance)
- **Converter**: `k8s/convert_genai_perf_results.py` (runs on GCP instance)
- **Full Guide**: `k8s/GENAI_PERF_GUIDE.md`
- **Dashboard**: `dashboard/comparative_dashboard.py`

## Quick Commands

```bash
# Run benchmark with defaults
./scripts/run_genai_perf_baseline.sh

# Run with custom settings
./scripts/run_genai_perf_baseline.sh 20 200

# View results
cat results/baseline/k8s/genai-perf-results.json | python3 -m json.tool

# Compare with custom benchmark
diff <(jq -S . results/baseline/k8s/all-models-results.json) \
     <(jq -S . results/baseline/k8s/genai-perf-results.json)
```
