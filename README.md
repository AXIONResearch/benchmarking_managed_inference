# ModelsGuard Inference Benchmark

Benchmarking framework to compare **baseline vLLM inference** vs **managed/optimized inference** (with KVCached and smart load balancing) across a heterogeneous multi-model setup.

## Overview

This project benchmarks vLLM performance improvements using:
- **KVCached**: Elastic KV cache management via CUDA VMM
- **Smart Load Balancing**: Queue-aware request routing
- **Multi-model Setup**: 5 different models across 6x H100 GPUs

## Infrastructure

- **Cloud**: GCP
- **GPUs**: 6x H100 80GB (single node)
- **OS**: Ubuntu 22.04 + CUDA 12.x

## Model Configuration

| Pod | GPU(s) | Model | HF Path | Port |
|-----|--------|-------|---------|------|
| 0 | 0 | Llama 3.1 8B | `meta-llama/Llama-3.1-8B-Instruct` | 8001 |
| 1 | 1 | Qwen 2.5 7B | `Qwen/Qwen2.5-7B-Instruct` | 8002 |
| 2 | 2 | Mistral 7B | `mistralai/Mistral-7B-Instruct-v0.3` | 8003 |
| 3 | 3 | Gemma 2 9B | `google/gemma-2-9b-it` | 8004 |
| 4 | 4,5 | Llama 3.1 70B (TP=2) | `meta-llama/Llama-3.1-70B-Instruct` | 8005 |

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
│   │   ├── nginx.conf
│   │   └── .env.example
│   └── managed/        # Managed vLLM + KVCached
│       ├── docker-compose.yml
│       ├── smart-lb/   # Smart load balancer
│       └── .env.example
├── benchmark/          # Benchmark framework
│   ├── run.py          # Main benchmark runner
│   ├── clients/        # Client implementations
│   └── workloads/      # Workload configurations
├── scripts/            # Deployment & execution scripts
│   ├── deploy.sh
│   ├── teardown.sh
│   └── run_benchmark.sh
├── results/            # Benchmark outputs
│   ├── baseline/
│   └── managed/
└── analysis/           # Comparison & visualization
    └── compare.py
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

**Run Baseline Benchmark:**

```bash
./scripts/run_benchmark.sh baseline 100 10
```

**Teardown Baseline:**

```bash
./scripts/teardown.sh baseline
```

**Deploy Managed:**

```bash
./scripts/deploy.sh managed
```

**Run Managed Benchmark:**

```bash
./scripts/run_benchmark.sh managed 100 10
```

### 4. Compare Results

```bash
python3 analysis/compare.py
```

This will generate a comparison report showing improvements in:
- TTFT (Time to First Token)
- End-to-end latency
- Throughput (requests/sec, tokens/sec)
- GPU memory utilization

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

### Baseline Setup

- **5 vLLM pods** (vanilla `vllm/vllm-openai:v0.6.4.post1`)
- **Nginx** round-robin load balancer
- `--enable-prefix-caching`
- Dedicated GPU per pod

### Managed Setup

- **5 KVCached vLLM pods** (`ghcr.io/ovg-project/kvcached-vllm:latest`)
- **Smart load balancer** (FastAPI, queue-aware)
- `ENABLE_KVCACHED=true`
- `--no-enable-prefix-caching` (required for KVCached)

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
