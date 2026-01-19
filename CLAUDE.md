# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Benchmarking framework comparing **baseline vLLM inference** vs **managed/optimized inference** (KVCached + smart load balancing) in multi-tenant, heterogeneous model environments.

**Goal:** Prove that managed inference (with KVCached and queue-aware load balancing) outperforms vanilla vLLM with simple round-robin routing.

## Deployment Architectures

The project supports **two deployment methods** - choose based on your use case:

### 1. Kubernetes (K3s) - **Current Primary Focus**
- Location: `k8s/`
- Platform: K3s on GCP with 8x L4 GPUs (6 allocated)
- Load Balancing: Native kube-proxy (ClusterIP Services)
- Namespaces: `baseline` and `managed`
- Model configuration: 3 models × 2 replicas = 6 pods

**K8s Models:**
- `meta-llama/Llama-3.1-8B-Instruct` (2 replicas, 1 GPU each)
- `Qwen/Qwen2.5-7B-Instruct` (2 replicas, 1 GPU each)
- `mistralai/Mistral-7B-Instruct-v0.3` (2 replicas, 1 GPU each)

### 2. Docker Compose - **Legacy**
- Location: `docker/baseline/` and `docker/managed/`
- Platform: Single node with 6x H100 GPUs
- Load Balancing: Custom FastAPI load balancers
- Ports: 8080 (baseline), 8081 (managed)
- Model configuration: 3 models × 2 replicas = 6 containers

**Docker Models:**
- `meta-llama/Llama-3.1-8B-Instruct` (2 replicas, 1 GPU each)
- `Qwen/Qwen2.5-7B-Instruct` (2 replicas, 1 GPU each)
- `mistralai/Mixtral-8x7B-Instruct-v0.1` (2 replicas, tensor parallel across 2 GPUs)

### Load Balancer Implementations

**Baseline (`simple-lb/app.py`):**
- Uses Python's `itertools.cycle()` for stateless round-robin
- Maps each model to its replica endpoints
- No state, no metrics, just cycling through replicas
- Example: Llama 8B requests alternate between endpoints[0] and endpoints[1]

**Managed (`smart-lb/app.py`):**
- Background task polls vLLM `/metrics` endpoints every 1 second
- Parses Prometheus metrics to extract `vllm:num_requests_waiting`
- Routes to replica with **lowest queue depth** for the requested model
- Falls back to first replica if metrics unavailable

## Common Development Commands

### Infrastructure Setup

```bash
# Deploy GCP infrastructure (from terraform/)
terraform init
terraform apply
INSTANCE_IP=$(terraform output -raw instance_ip)

# SSH to instance
ssh ubuntu@$INSTANCE_IP
```

### Environment Setup

```bash
# Configure baseline
cp docker/baseline/.env.example docker/baseline/.env
# Edit and add HF_TOKEN

# Configure managed
cp docker/managed/.env.example docker/managed/.env
# Edit and add HF_TOKEN
```

### Deployment

```bash
# Deploy baseline environment
./scripts/deploy.sh baseline

# Deploy managed environment
./scripts/deploy.sh managed

# Teardown specific environment
./scripts/teardown.sh baseline
./scripts/teardown.sh managed

# Teardown all
./scripts/teardown.sh all
```

### Health Checks

```bash
# Check load balancer health
curl http://localhost:8080/health  # Baseline
curl http://localhost:8081/health  # Managed

# Check individual pod
curl http://localhost:8001/v1/models  # Llama 8B replica 1
curl http://localhost:8005/v1/models  # Mixtral 8x7B replica 1

# View logs
docker logs -f vllm-llama-8b-1
docker logs -f vllm-mixtral-8x7b-1
docker logs -f baseline-simple-lb
docker logs -f managed-smart-lb
```

### Benchmarking

**Kubernetes (Current):**
```bash
# Custom OpenAI client benchmark (runs on K8s)
python3 k8s/benchmark_k8s.py
# Results: /tmp/all-models-results.json → copy to results/baseline/k8s/

# GenAI-Perf via automated script (recommended)
./scripts/run_genai_perf_baseline.sh  # Runs everything automatically
# - Uploads scripts to GCP
# - Runs GenAI-Perf on all models
# - Converts results
# - Downloads to results/baseline/k8s/genai-perf-results.json

# Manual GenAI-Perf (on GCP instance)
ssh -i ~/.ssh/google_compute_engine davidengstler@<INSTANCE_IP>
./genai_perf_k8s.sh baseline 10 100
python3 convert_genai_perf_results.py /tmp/genai_perf_k8s_* --namespace baseline
# Results: results/baseline/k8s/genai-perf-results.json
```

**Docker Compose (Legacy):**
```bash
# Install GenAI-Perf (requires Python 3.10+ and CUDA 12)
pip3 install genai-perf

# Benchmark all models
./scripts/benchmark_all_models.sh baseline 10 100

# Benchmark specific model
./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.1-8B-Instruct" 10 100
```

**Results Structure:**
```
results/
├── baseline/
│   └── k8s/
│       ├── all-models-results.json      # Custom benchmark
│       └── genai-perf-results.json      # GenAI-Perf benchmark
└── managed/
    └── k8s/
        ├── all-models-results.json
        └── genai-perf-results.json
```

## Benchmarking Dashboard

Interactive Streamlit dashboard for viewing and comparing results:

```bash
# Start dashboard
cd dashboard
streamlit run comparative_dashboard.py

# Or use existing instance
open http://localhost:8501
```

**Features:**
- **Benchmark Type Selector**: Custom, GenAI-Perf, or Both (comparison)
- **View Modes**: Single Environment, Side-by-Side Comparison, Overlay Comparison
- **Automatic Detection**: Loads both custom and GenAI-Perf results
- **Metrics**: Requests/sec, latency (mean, median, P95, P99), tokens/sec, success rate
- **Visualizations**: Bar charts, grouped comparisons, latency percentiles

**Dashboard Files:**
- `dashboard/comparative_dashboard.py` - Main comparative dashboard
- `dashboard/k8s_results_dashboard.py` - K8s baseline-only view

## Key Implementation Details

### Kubernetes Deployments

**Deployment Structure (K8s):**
- Each model has its own Deployment with 2 replicas
- Each pod gets 1 dedicated GPU via `nvidia.com/gpu: 1`
- ClusterIP Services provide native load balancing (kube-proxy)
- Model cache shared via hostPath: `/mnt/model-cache/huggingface`

**Key K8s Files:**
- `k8s/baseline/*.yaml` - K8s manifests for baseline namespace
- `k8s/deploy-baseline.sh` - Deployment automation script
- `k8s/benchmark_k8s.py` - Custom Python benchmark for K8s
- `k8s/genai_perf_k8s.sh` - GenAI-Perf runner via port-forward
- `k8s/convert_genai_perf_results.py` - Converts GenAI-Perf output to dashboard format

**Adding Models (K8s):**
1. Create new deployment YAML in `k8s/baseline/` or `k8s/managed/`
2. Update `k8s/benchmark_k8s.py` models list
3. Update `k8s/genai_perf_k8s.sh` MODELS array
4. Update dashboard model mapping in `dashboard/comparative_dashboard.py`

### Docker Compose Load Balancers

**Model-to-Endpoint Mapping (Docker only):**

When adding or changing models in Docker deployments:

1. Update `docker-compose.yml` for both baseline and managed
2. Update model mappings in **both** load balancers:
   - `docker/baseline/simple-lb/app.py` - `RoundRobinSelector.model_endpoints`
   - `docker/managed/smart-lb/app.py` - `EndpointSelector.get_best_endpoint()`
3. Update `VLLM_ENDPOINTS` env var in docker-compose files (6 comma-separated URLs)

### Tensor Parallelism

Mixtral 8x7B uses tensor parallelism across 2 GPUs:
- vLLM flag: `--tensor-parallel-size 2`
- Applied in both baseline and managed docker-compose files
- Distributes the MoE model (~47B params) across 2x L4 GPUs (48GB total)
- No quantization needed - runs in BF16/FP16

### Environment Variables

**Required:**
- `HF_TOKEN` - HuggingFace token (in `.env` files)

**Load Balancer Config:**
- `VLLM_ENDPOINTS` - Comma-separated list of 6 backend URLs
- `METRICS_POLL_INTERVAL` - Polling frequency in seconds (managed only, default: 1)

### Metrics Parsing

The smart load balancer parses Prometheus-format metrics from vLLM's `/metrics` endpoint:

```python
# Example metric line:
# vllm:num_requests_waiting 3.0

for line in metrics_text.split('\n'):
    if 'vllm:num_requests_waiting' in line and not line.startswith('#'):
        queue_depth = float(line.split()[-1])
```

## Terraform Infrastructure

**Current (K8s):**
- Machine type: `a3-highgpu-1g` (8x L4 GPUs, 6 allocated)
- Platform: Ubuntu 22.04 + CUDA 12.x + K3s
- Startup script installs: Docker, K3s, NVIDIA Container Toolkit, kubectl
- Firewall: Opens ports 22, 6443 (K8s API), 30000-32767 (NodePort range)

**Legacy (Docker):**
- Machine type: `a3-highgpu-8g` (8x H100 GPUs, we use 6)
- Platform: Ubuntu 22.04 + CUDA 12.4 + Docker Compose
- Firewall: Opens ports 8001-8006, 8080, 8081, 22

## Troubleshooting Notes

### Kubernetes-Specific

**Pods not starting:**
```bash
# Check pod status
sudo k3s kubectl get pods -n baseline
sudo k3s kubectl describe pod <pod-name> -n baseline
sudo k3s kubectl logs <pod-name> -n baseline

# Check GPU allocation
sudo k3s kubectl get nodes -o json | jq '.items[].status.allocatable'

# Common fixes:
# - Verify HF_TOKEN secret: kubectl get secret -n baseline huggingface-token
# - Check GPU availability: nvidia-smi
# - Ensure model cache exists: ls /mnt/model-cache/huggingface
```

**GenAI-Perf port-forward issues:**
```bash
# Verify service exists
sudo k3s kubectl get svc -n baseline

# Manual port-forward test
sudo k3s kubectl port-forward -n baseline service/vllm-llama-8b 9000:8000
curl http://localhost:9000/health

# Check if port is already in use
sudo lsof -i :9000
```

**Dashboard not showing results:**
```bash
# Verify result files exist locally
ls -la results/baseline/k8s/
cat results/baseline/k8s/all-models-results.json | python3 -m json.tool

# Restart dashboard
pkill -f streamlit
cd dashboard && streamlit run comparative_dashboard.py
```

### General (Both Platforms)

**Models not loading:**
- Verify HF_TOKEN is set correctly (K8s: secret, Docker: `.env`)
- Check HuggingFace account has access to gated models (Llama requires approval)
- Check disk space: `df -h`
- Check logs: `docker logs` or `kubectl logs`

**OOM errors:**
- Reduce `--gpu-memory-utilization` from 0.95 to 0.90
- Ensure only one environment (baseline OR managed) runs at a time
- Check GPU memory: `nvidia-smi`

**Load balancer not routing (Docker only):**
- Check `VLLM_ENDPOINTS` has exactly 6 URLs
- Verify endpoint ordering matches pod layout
- For managed: check metrics endpoint is accessible

**SSH/Connection issues:**
- Update known_hosts if host key changed: `ssh-keygen -R <INSTANCE_IP>`
- Use `-o StrictHostKeyChecking=no` for automation
- Verify firewall rules in GCP console

## GenAI-Perf Benchmarking Workflow

### Automated (Recommended)

Single command that handles everything:

```bash
# From project root on local machine
./scripts/run_genai_perf_baseline.sh [concurrency] [request_count]

# Examples:
./scripts/run_genai_perf_baseline.sh           # Defaults: 10 concurrent, 100 requests
./scripts/run_genai_perf_baseline.sh 20 200    # Custom: 20 concurrent, 200 requests
```

**What it does:**
1. Uploads `genai_perf_k8s.sh` and `convert_genai_perf_results.py` to GCP instance
2. Runs GenAI-Perf against all 3 models using kubectl port-forward
3. Converts results from CSV/JSON to dashboard format
4. Downloads `genai-perf-results.json` to `results/baseline/k8s/`
5. Displays summary metrics

**Duration:** ~10-15 minutes for all 3 models

### Manual Steps

If you need to run steps individually:

```bash
# 1. Upload scripts (from local machine)
INSTANCE_IP=$(cd terraform && terraform output -raw instance_ip)
scp -i ~/.ssh/google_compute_engine \
  k8s/genai_perf_k8s.sh \
  k8s/convert_genai_perf_results.py \
  davidengstler@$INSTANCE_IP:~/

# 2. SSH to instance and run
ssh -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP
chmod +x genai_perf_k8s.sh
./genai_perf_k8s.sh baseline 10 100

# 3. Convert results (on instance)
RESULTS_DIR=$(ls -td /tmp/genai_perf_k8s_* | head -1)
python3 convert_genai_perf_results.py "$RESULTS_DIR" --namespace baseline
ls -la results/baseline/k8s/genai-perf-results.json

# 4. Download results (from local machine)
scp -i ~/.ssh/google_compute_engine \
  davidengstler@$INSTANCE_IP:results/baseline/k8s/genai-perf-results.json \
  results/baseline/k8s/
```

### GenAI-Perf Parameters

**NOTE**: GenAI-Perf v0.0.16+ has changed CLI syntax. The `genai_perf_k8s.sh` script may need updates.

**Current script uses (may be outdated):**
```bash
genai-perf profile \
  -m "$MODEL" \                         # Model name (must match K8s deployment)
  --service-kind openai \               # vLLM uses OpenAI-compatible API
  --endpoint v1/chat/completions \      # Chat completion endpoint
  --endpoint-type chat \                # Chat mode (vs completions)
  --url "http://localhost:$PORT" \      # Port-forwarded service
  --streaming \                         # Enable streaming responses
  --concurrency "$CONCURRENCY" \        # Concurrent requests (default: 10)
  --num-prompts "$REQUEST_COUNT" \      # Total requests (default: 100)
  --random-seed 123 \                   # Reproducibility
  --synthetic-input-tokens-mean 100 \   # Average prompt length
  --synthetic-input-tokens-stddev 20 \  # Prompt length variation
  --tokenizer "$MODEL"                  # Use model's tokenizer
```

**If you encounter `error: unrecognized arguments: --service-kind`:**
- GenAI-Perf CLI has changed in v0.0.16+
- Check updated syntax: `genai-perf profile --help`
- May need to use subcommands like `genai-perf profile openai` instead
- Refer to: https://github.com/triton-inference-server/perf_analyzer

**Key Metrics Captured:**
- **Request Throughput**: Requests per second
- **Time to First Token (TTFT)**: Latency until first token
- **Inter-Token Latency (ITL)**: Time between tokens
- **End-to-End Latency**: Total request time
- **Percentiles**: P50, P95, P99 for all metrics
- **Tokens per Second**: Generation throughput

## Quick Reference

### Most Common Commands

```bash
# Get instance IP
cd terraform && terraform output -raw instance_ip

# SSH to instance
ssh -i ~/.ssh/google_compute_engine davidengstler@$(cd terraform && terraform output -raw instance_ip)

# Check K8s pods
sudo k3s kubectl get pods -n baseline -o wide

# Check pod logs
sudo k3s kubectl logs -n baseline vllm-llama-8b-0 --tail=50

# Run GenAI-Perf benchmark (automated)
./scripts/run_genai_perf_baseline.sh

# Run custom benchmark on instance
python3 k8s/benchmark_k8s.py

# View dashboard locally
open http://localhost:8501

# Download K8s results
scp -i ~/.ssh/google_compute_engine \
  davidengstler@$(cd terraform && terraform output -raw instance_ip):results/baseline/k8s/*.json \
  results/baseline/k8s/
```

### File Locations Reference

**Kubernetes Deployments:**
- `k8s/baseline/*.yaml` - Baseline K8s manifests
- `k8s/deploy-baseline.sh` - Deployment script
- `k8s/benchmark_k8s.py` - Custom Python benchmark
- `k8s/genai_perf_k8s.sh` - GenAI-Perf runner
- `k8s/convert_genai_perf_results.py` - Results converter

**Benchmarking:**
- `scripts/run_genai_perf_baseline.sh` - Automated GenAI-Perf
- `results/baseline/k8s/all-models-results.json` - Custom benchmark results
- `results/baseline/k8s/genai-perf-results.json` - GenAI-Perf results

**Dashboard:**
- `dashboard/comparative_dashboard.py` - Main dashboard
- `dashboard/k8s_results_dashboard.py` - K8s-only view

**Documentation:**
- `k8s/GENAI_PERF_GUIDE.md` - Detailed GenAI-Perf guide
- `scripts/README_GENAI_PERF.md` - Automation script docs
- `CLAUDE.md` - This file

### Port Reference

**Kubernetes (via port-forward):**
- Services are ClusterIP (internal only)
- Use `kubectl port-forward` to access from outside cluster
- Default port-forward: 9000 → service:8000

**Docker Compose (Legacy):**
- 8001: Llama 8B replica 1
- 8002: Llama 8B replica 2
- 8003: Qwen 7B replica 1
- 8004: Qwen 7B replica 2
- 8005: Mixtral 8x7B replica 1 (tensor parallel)
- 8006: Mixtral 8x7B replica 2 (tensor parallel)
- 8080: Baseline load balancer
- 8081: Managed load balancer

**Local:**
- 8501: Streamlit dashboard
- NEVER UNDER ANY CIRCUMNSTANCE YOU WILL CREATE MOCK DATA WITHOUT MY PERMISSION