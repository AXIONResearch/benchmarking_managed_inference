# ModelsGuard Inference Benchmark

Benchmarking framework to compare **baseline vLLM inference** vs **managed/optimized inference** (with KVCached and smart load balancing) across a heterogeneous multi-model setup.

## 📋 Table of Contents

- **NEW: [Kubernetes Deployment](#-quick-start---kubernetes-deployment)** ← Start here for K8s on GCP
- [Docker Compose Deployment (Legacy)](#-docker-compose-deployment-legacy)
- [Dashboard](#-dashboard-features)
- [Documentation](#-documentation)

## Overview

This project benchmarks vLLM performance improvements using:
- **KVCached**: Elastic KV cache management via CUDA VMM
- **Smart Load Balancing**: Queue-aware request routing (vs. model-aware round-robin)
- **Multi-model Setup**: 3 models with 2 replicas each
- **GenAI-Perf**: Industry-standard benchmarking tool from Triton Inference Server
- **Two Deployment Options**: Kubernetes (K3s) or Docker Compose

## 🆕 Kubernetes Deployment (Recommended)

### Infrastructure

- **Cloud**: GCP Compute Engine
- **GPUs**: 8x L4 GPUs (6 allocated for models)
- **Platform**: K3s (lightweight Kubernetes)
- **OS**: Ubuntu 22.04 + CUDA 12.x

### Centralized Configuration

All model configurations are defined in `config/models.yaml` for easy modification:

```yaml
models:
  - name: "llama-8b"
    full_name: "meta-llama/Llama-3.1-8B-Instruct"
    replicas: 2
    gpu_count: 1
```

This single source of truth simplifies:
- Adding/removing models
- Changing replica counts
- Updating GPU allocations
- Switching between environments (baseline vs managed)

### Model Configuration (K8s)

| Model | Replicas | GPUs per Pod | Service Name |
|-------|----------|--------------|--------------|
| Llama-3.1-8B | 2 | 1 | `vllm-llama-8b` |
| Qwen2.5-7B | 2 | 1 | `vllm-qwen-7b` |
| Mistral-7B | 2 | 1 | `vllm-mistral-7b` |

**Total**: 6 pods using 6 GPUs with native kube-proxy load balancing

---

## 🚀 Quick Start - Kubernetes Deployment

### Prerequisites

1. **GCP Account** with GPU quota
2. **HuggingFace Token** with access to gated models ([get one here](https://huggingface.co/settings/tokens))
3. **Local Tools**: Terraform >= 1.0, SSH client

### Step 1: Deploy Infrastructure with Terraform

```bash
cd terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy GCP instance with 8x L4 GPUs + K3s
terraform apply
# Type 'yes' when prompted

# Save the instance IP
INSTANCE_IP=$(terraform output -raw instance_ip)
echo "Instance IP: $INSTANCE_IP"
```

**What gets created:**
- GCP instance (`a3-highgpu-1g`) with 8x L4 GPUs
- K3s Kubernetes cluster
- NVIDIA Container Toolkit + CUDA 12.x
- Firewall rules for SSH and K8s

**Time**: ~5-10 minutes

### Step 2: Deploy Baseline vLLM on K8s

```bash
# SSH to the instance
ssh -i ~/.ssh/google_compute_engine davidengstler@$INSTANCE_IP

# Upload K8s deployment files (from local machine, before SSH)
scp -i ~/.ssh/google_compute_engine -r k8s/ davidengstler@$INSTANCE_IP:~/

# On the GCP instance, run the deployment script
cd ~/k8s
chmod +x deploy-baseline.sh
HF_TOKEN=hf_YOUR_TOKEN_HERE ./deploy-baseline.sh
```

**What this does:**
1. Creates `baseline` namespace
2. Creates HuggingFace token secret
3. Deploys 6 model pods (3 models × 2 replicas)
4. Creates ClusterIP services with kube-proxy load balancing
5. Waits for all pods to be ready

**Time**: 3-5 minutes for deployment + 3-5 minutes for models to download (first time only)

### Step 3: Verify Deployment

```bash
# Check pods (on GCP instance)
sudo k3s kubectl get pods -n baseline -o wide

# Expected output:
# vllm-llama-8b-0     1/1  Running
# vllm-llama-8b-1     1/1  Running
# vllm-qwen-7b-0      1/1  Running
# vllm-qwen-7b-1      1/1  Running
# vllm-mistral-7b-0   1/1  Running
# vllm-mistral-7b-1   1/1  Running

# Check services
sudo k3s kubectl get svc -n baseline

# Test a service
sudo k3s kubectl port-forward -n baseline service/vllm-llama-8b 9000:8000 &
curl http://localhost:9000/v1/models
```

### Step 4: Run Benchmarks

**Option A: Automated (Recommended)** - From your local machine:

```bash
# Run GenAI-Perf against all models
./scripts/run_genai_perf_baseline.sh

# This fully automates:
# 1. Upload scripts to GCP
# 2. Run GenAI-Perf benchmarks (~10-15 min)
# 3. Convert results to dashboard format
# 4. Download results to results/baseline/k8s/
```

**Option B: Manual** - On GCP instance:

```bash
# Custom Python benchmark
python3 ~/k8s/benchmark_k8s.py
# Results: /tmp/all-models-results.json
```

### Step 5: View Results in Dashboard

From your local machine:

```bash
cd dashboard
streamlit run comparative_dashboard.py
# Opens at http://localhost:8501

# Select "GenAI-Perf" from the benchmark type dropdown
# Choose your view mode (Single, Side-by-Side, or Overlay)
```

### Clean Up

```bash
# Delete K8s deployments (on GCP instance)
sudo k3s kubectl delete namespace baseline

# Destroy infrastructure (from local machine)
cd terraform
terraform destroy
```

---

## 📊 Dashboard Features

The Streamlit dashboard (`dashboard/comparative_dashboard.py`) provides:

- **Benchmark Type Selector**: Custom, GenAI-Perf, or Both (comparison)
- **View Modes**: Single Environment, Side-by-Side, Overlay
- **Metrics**: Requests/sec, latency (mean, P95, P99), tokens/sec, success rate
- **Interactive Charts**: Plotly visualizations with drill-down

---

## 🔧 Kubernetes Management

### Common Operations

```bash
# View logs
sudo k3s kubectl logs -n baseline vllm-llama-8b-0 --tail=50

# Restart a pod
sudo k3s kubectl delete pod vllm-llama-8b-0 -n baseline

# Check GPU allocation
sudo k3s kubectl get nodes -o json | jq '.items[].status.allocatable'

# Port-forward to test endpoints
sudo k3s kubectl port-forward -n baseline service/vllm-qwen-7b 9000:8000
```

### Troubleshooting K8s

**Pods stuck in Pending:**
```bash
# Check GPU availability
nvidia-smi
sudo k3s kubectl get pods -n kube-system | grep nvidia
```

**Models not loading:**
```bash
# Verify HuggingFace secret
sudo k3s kubectl get secret -n baseline huggingface-token
sudo k3s kubectl get secret huggingface-token -n baseline -o jsonpath='{.data.token}' | base64 -d
```

---

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete technical documentation
- **[k8s/GENAI_PERF_GUIDE.md](k8s/GENAI_PERF_GUIDE.md)** - GenAI-Perf benchmarking guide
- **[scripts/README_GENAI_PERF.md](scripts/README_GENAI_PERF.md)** - Automation script docs

---

## 🐳 Docker Compose Deployment (Legacy)

The original Docker Compose deployment is still available for H100 instances. See sections below for Docker-specific instructions.

### Infrastructure (Docker)

- **Cloud**: GCP
- **GPUs**: 6x H100 80GB (single node)
- **OS**: Ubuntu 22.04 + CUDA 12.x

### Model Configuration (Docker)

**Pod Layout:** 3 models with replication for high availability and load distribution

| Pod | GPU | Model | HF Path | Port | Notes |
|-----|-----|-------|---------|------|-------|
| 0 | 0 | Llama 3.1 8B (R1) | `meta-llama/Llama-3.1-8B-Instruct` | 8001 | Small model replica 1 |
| 1 | 1 | Llama 3.1 8B (R2) | `meta-llama/Llama-3.1-8B-Instruct` | 8002 | Small model replica 2 |
| 2 | 2 | Qwen 2.5 7B (R1) | `Qwen/Qwen2.5-7B-Instruct` | 8003 | Small model replica 1 |
| 3 | 3 | Qwen 2.5 7B (R2) | `Qwen/Qwen2.5-7B-Instruct` | 8004 | Small model replica 2 |
| 4 | 4 | Llama 3.3 70B (R1) | `meta-llama/Llama-3.3-70B-Instruct` | 8005 | Large model, AWQ 4-bit |
| 5 | 5 | Llama 3.3 70B (R2) | `meta-llama/Llama-3.3-70B-Instruct` | 8006 | Large model, AWQ 4-bit |

**Benefits of this layout:**
- **Load Distribution**: 2 replicas per model allow load balancing
- **High Availability**: Replica redundancy ensures service continuity
- **Real-world Scenario**: Mimics multi-tenant production environments

## Directory Structure

```
.
├── terraform/          # GCP infrastructure (6x H100 instance)
│   ├── main.tf
│   ├── variables.tf
│   └── startup.sh
├── docker/
│   ├── baseline/       # Baseline vLLM setup
│   │   ├── docker-compose.yml
│   │   ├── simple-lb/  # Model-aware round-robin LB
│   │   └── .env.example
│   └── managed/        # Managed vLLM + KVCached
│       ├── docker-compose.yml
│       ├── smart-lb/   # Queue-aware smart LB
│       └── .env.example
├── benchmark/          # Benchmark framework
│   └── genai_perf_runner.sh  # GenAI-Perf benchmark runner
├── scripts/            # Deployment & execution scripts
│   ├── deploy.sh
│   ├── teardown.sh
│   ├── test_baseline.sh
│   ├── benchmark_all_models.sh
│   └── gcp_quick_deploy.sh
└── results/            # Benchmark outputs (GenAI-Perf)
    ├── baseline/
    └── managed/
```

## Quick Start

### 1. Infrastructure Setup

```bash
# Configure GCP credentials
gcloud auth login

# Navigate to terraform directory
cd terraform

# Copy and edit terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project ID

# Deploy infrastructure
terraform init
terraform plan
terraform apply

# Note the instance IP
INSTANCE_IP=$(terraform output -raw instance_ip)
```

### 2. Configure Environment

SSH into the instance:

```bash
ssh ubuntu@$INSTANCE_IP
```

Clone the repository and configure:

```bash
git clone <your-repo-url>
cd benchmarking_managed_inference

# Set up baseline environment
cp docker/baseline/.env.example docker/baseline/.env
# Edit docker/baseline/.env and add your HF_TOKEN

# Set up managed environment
cp docker/managed/.env.example docker/managed/.env
# Edit docker/managed/.env and add your HF_TOKEN
```

### 3. Deploy and Benchmark

**Deploy Baseline:**

```bash
./scripts/deploy.sh baseline
```

**Run Baseline Benchmark (GenAI-Perf):**

```bash
# Install genai-perf (requires Python 3.10+ and CUDA 12)
pip3 install genai-perf

# Benchmark all 3 models (Llama 8B, Qwen 7B, Llama 70B)
./scripts/benchmark_all_models.sh baseline 10 100

# Or benchmark a specific model
./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.1-8B-Instruct" 10 100
```

**Teardown Baseline:**

```bash
./scripts/teardown.sh baseline
```

**Deploy Managed:**

```bash
./scripts/deploy.sh managed
```

**Run Managed Benchmark (GenAI-Perf):**

```bash
./scripts/benchmark_all_models.sh managed 10 100
```

### 4. Analyze Results

GenAI-Perf automatically generates comprehensive reports in `results/[baseline|managed]/genai_perf_*/`:

**Automatic Outputs:**
- `profile_export.csv` - Detailed metrics in CSV format
- `profile_export.json` - JSON formatted results
- Performance plots (with `--generate-plots` flag)

**Key Metrics Measured:**
- **TTFT**: Time to First Token (P50, P90, P99, P99.9)
- **ITL**: Inter-Token Latency
- **Request Latency**: End-to-end latency (P50, P90, P99)
- **Output Token Throughput**: Tokens/sec
- **Request Throughput**: Requests/sec
- **GPU Telemetry**: Power usage, memory utilization, GPU utilization

**Custom Analysis:**
```bash
# Compare baseline vs managed using custom script
python3 analysis/compare.py
```

## Benchmark Metrics

The framework measures:

- **TTFT**: Time to first token (P50, P90, P99)
- **E2E Latency**: End-to-end request latency (P50, P90, P99)
- **Throughput**: Requests/sec, Tokens/sec
- **Success Rate**: % of successful requests

## Customization

### Custom Workload

Create a custom workload configuration:

```json
{
  "models": ["meta-llama/Llama-3.1-8B-Instruct"],
  "prompts": ["Your custom prompts here"],
  "max_tokens_range": [128, 512],
  "temperature_range": [0.7, 1.0]
}
```

Run with custom workload:

```bash
python3 benchmark/run.py \
  --env baseline \
  --workload path/to/custom.json \
  --num-requests 200 \
  --concurrency 20
```

### Adjust Concurrency

Test different concurrency levels:

```bash
./scripts/run_benchmark.sh baseline 1000 50
```

## Architecture

### Baseline Setup (Control)

- **6 vLLM pods** (vanilla `vllm/vllm-openai:v0.6.4.post1`)
  - 2x Llama 3.1 8B replicas (GPUs 0-1)
  - 2x Qwen 2.5 7B replicas (GPUs 2-3)
  - 2x Llama 3.3 70B replicas (GPUs 4-5, AWQ 4-bit quantized)
- **Model-Aware Round-Robin LB** (FastAPI)
  - Simple round-robin cycling through replicas of each model
  - No queue monitoring, purely stateless round-robin
  - Routes based on model name in request
- `--enable-prefix-caching`
- `--quantization awq` (for 70B model)
- Dedicated GPU per pod (1:1 mapping)

### Managed Setup (Optimized)

- **6 KVCached vLLM pods** (`ghcr.io/ovg-project/kvcached-vllm:latest`)
  - Same model configuration as baseline
  - Same quantization strategy
- **Smart Load Balancer** (FastAPI, queue-aware)
  - Routes to **least busy** replica of requested model
  - Real-time queue depth monitoring via `/metrics` endpoint
  - Polls metrics every 1 second
  - Intelligent routing based on actual load
- `ENABLE_KVCACHED=true` (elastic KV cache via CUDA VMM)
- `--no-enable-prefix-caching` (required for KVCached)
- `--quantization awq` (for 70B model)

**Key Difference:** Managed uses queue-aware routing + KVCached, Baseline uses simple round-robin + standard vLLM caching

## Troubleshooting

**Check service health:**

```bash
# Baseline
curl http://localhost:8080/health

# Managed
curl http://localhost:8081/health
```

**View logs:**

```bash
# Baseline
cd docker/baseline && docker-compose logs -f

# Managed
cd docker/managed && docker-compose logs -f
```

**Check GPU utilization:**

```bash
nvidia-smi
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm)
- [KVCached](https://github.com/ovg-project/kvcached-vllm)
