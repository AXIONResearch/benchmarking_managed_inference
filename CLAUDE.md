# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a benchmarking framework to compare **baseline vLLM inference** vs **managed/optimized inference** (KVCached + smart load balancing) in a multi-tenant, heterogeneous model environment on 6x H100 GPUs.

**Goal:** Prove that managed inference (with KVCached and queue-aware load balancing) outperforms vanilla vLLM with simple round-robin routing.

## Architecture

### Two Parallel Environments

The project maintains two independent but identically-configured inference setups:

1. **Baseline (Control)** - `docker/baseline/`
   - 6 vanilla vLLM pods (`vllm/vllm-openai:v0.6.4.post1`)
   - Simple model-aware round-robin load balancer (`simple-lb/app.py`)
   - Uses `--enable-prefix-caching`
   - Port 8080

2. **Managed (Optimized)** - `docker/managed/`
   - 6 KVCached vLLM pods (`ghcr.io/ovg-project/kvcached-vllm:latest`)
   - Queue-aware smart load balancer (`smart-lb/app.py`)
   - Uses `ENABLE_KVCACHED=true` and `--no-enable-prefix-caching`
   - Port 8081

### Pod Layout (6 Pods, 3 Models, 2 Replicas Each)

**Critical:** The endpoint ordering in load balancers must match this exact mapping:

```
endpoints[0] = GPU 0 = Llama 8B Replica 1        (port 8001)
endpoints[1] = GPU 1 = Llama 8B Replica 2        (port 8002)
endpoints[2] = GPU 2 = Qwen 7B Replica 1         (port 8003)
endpoints[3] = GPU 3 = Qwen 7B Replica 2         (port 8004)
endpoints[4] = GPU 4-5 = Mixtral 8x7B Replica 1  (port 8005, tensor parallel)
endpoints[5] = GPU 6-7 = Mixtral 8x7B Replica 2  (port 8006, tensor parallel)
```

Models:
- `meta-llama/Llama-3.1-8B-Instruct` - Small model, 2 replicas, single GPU each
- `Qwen/Qwen2.5-7B-Instruct` - Small model, 2 replicas, single GPU each
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - Large MoE model, 2 replicas, **tensor parallel across 2 GPUs each**

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

```bash
# Install GenAI-Perf (requires Python 3.10+ and CUDA 12)
pip3 install genai-perf

# Benchmark all models in baseline
./scripts/benchmark_all_models.sh baseline 10 100

# Benchmark all models in managed
./scripts/benchmark_all_models.sh managed 10 100

# Benchmark specific model
./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.1-8B-Instruct" 10 100

# Custom benchmark (legacy Python client)
python3 benchmark/run.py --env baseline --num-requests 100 --concurrency 10
```

Results are saved to `results/[baseline|managed]/genai_perf_*/` with:
- `profile_export.csv` - Detailed metrics
- `profile_export.json` - JSON results
- Performance plots (if generated)

## Key Implementation Details

### Model-to-Endpoint Mapping

Both load balancers hardcode the model-to-endpoint mapping. When adding or changing models:

1. Update `docker-compose.yml` for both baseline and managed
2. Update model mappings in **both** load balancers:
   - `docker/baseline/simple-lb/app.py` - `RoundRobinSelector.model_endpoints`
   - `docker/managed/smart-lb/app.py` - `EndpointSelector.get_best_endpoint()`
3. Update `benchmark/workloads/default.json` - models list
4. Update `VLLM_ENDPOINTS` env var in docker-compose files (6 comma-separated URLs)

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

Target: GCP single-node with 6x H100 80GB GPUs
- Machine type: `a3-highgpu-8g` (has 8 GPUs, we use 6)
- Startup script installs: Docker, NVIDIA Container Toolkit, CUDA 12.4
- Firewall: Opens ports 8001-8006, 8080, 8081, 22

## Troubleshooting Notes

**Models not loading:**
- Verify HF_TOKEN is set correctly in `.env`
- Check HuggingFace account has access to gated models (Llama requires approval)
- Check disk space: `df -h`

**OOM errors:**
- Reduce `--gpu-memory-utilization` from 0.95 to 0.90 in docker-compose
- Ensure only one environment (baseline OR managed) runs at a time
- For Mixtral 8x7B, ensure `--tensor-parallel-size 2` is set and 2 GPUs are assigned

**Load balancer not routing:**
- Check `VLLM_ENDPOINTS` has exactly 6 URLs
- Verify endpoint ordering matches pod layout
- For managed: check metrics endpoint is accessible: `curl http://vllm-llama-8b-1:8000/metrics`

**GenAI-Perf fails:**
- Ensure CUDA 12 is installed
- Verify endpoint URL is correct (8080 for baseline, 8081 for managed)
- Check model name matches exactly (case-sensitive)
