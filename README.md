# ModelsGuard Inference Benchmark

Benchmarking framework to compare **baseline vLLM inference** vs **managed/optimized inference** (with KVCached and smart load balancing) across a heterogeneous multi-model setup.

## Overview

This project benchmarks vLLM performance improvements using:
- **KVCached**: Elastic KV cache management via CUDA VMM
- **Smart Load Balancing**: Queue-aware request routing (vs. model-aware round-robin)
- **Multi-model Setup**: 3 models with 2 replicas each across 6x H100 GPUs
- **GenAI-Perf**: Industry-standard benchmarking tool from Triton Inference Server

## Infrastructure

- **Cloud**: GCP
- **GPUs**: 6x H100 80GB (single node)
- **OS**: Ubuntu 22.04 + CUDA 12.x

## Model Configuration

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
