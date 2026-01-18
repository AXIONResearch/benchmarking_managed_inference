# Quick Start Guide

## Prerequisites

- GCP account with billing enabled
- HuggingFace account and token (for gated models)
- Terraform installed
- SSH key pair

## Step-by-Step Setup

### 1. Deploy GCP Infrastructure

```bash
cd terraform

# Copy and configure terraform variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values:
# - project_id: Your GCP project ID
# - region: GCP region (e.g., us-central1)
# - zone: GCP zone (e.g., us-central1-a)
# - ssh_public_key_path: Path to your SSH public key

# Initialize and deploy
terraform init
terraform apply

# Save the instance IP
INSTANCE_IP=$(terraform output -raw instance_ip)
echo $INSTANCE_IP
```

### 2. Connect to Instance

```bash
ssh ubuntu@$INSTANCE_IP
```

Wait for startup script to complete (~10-15 minutes). Check progress:

```bash
tail -f /var/log/syslog | grep startup-script
```

### 3. Clone and Configure

```bash
git clone https://github.com/davidaxion/benchmarking_managed_inference.git
cd benchmarking_managed_inference

# Configure baseline environment
cp docker/baseline/.env.example docker/baseline/.env
nano docker/baseline/.env  # Add your HF_TOKEN

# Configure managed environment
cp docker/managed/.env.example docker/managed/.env
nano docker/managed/.env  # Add your HF_TOKEN
```

### 4. Run Baseline Benchmark

```bash
# Deploy baseline
./scripts/deploy.sh baseline

# Wait for models to load (check with docker logs)
docker logs -f vllm-llama-8b

# Run benchmark
./scripts/run_benchmark.sh baseline 100 10

# View results
ls -la results/baseline/

# Teardown
./scripts/teardown.sh baseline
```

### 5. Run Managed Benchmark

```bash
# Deploy managed
./scripts/deploy.sh managed

# Wait for models to load
docker logs -f vllm-llama-8b-1-kvcached

# Run benchmark
./scripts/run_benchmark.sh managed 100 10

# View results
ls -la results/managed/
```

### 6. Compare Results

```bash
python3 analysis/compare.py
```

## Common Commands

**Check service health:**
```bash
# Baseline
curl http://localhost:8080/health

# Managed
curl http://localhost:8081/health
```

**View logs:**
```bash
# All containers
docker ps

# Specific container
docker logs -f <container_name>
```

**Monitor GPUs:**
```bash
watch -n 1 nvidia-smi
```

**Test individual pods:**
```bash
# Test Llama 8B replica 1
curl http://localhost:8001/v1/models

# Test Llama 8B replica 2
curl http://localhost:8002/v1/models

# Test Qwen 7B replicas
curl http://localhost:8003/v1/models
curl http://localhost:8004/v1/models

# Test Llama 70B replicas
curl http://localhost:8005/v1/models
curl http://localhost:8006/v1/models

# Send test request to Llama 70B
curl http://localhost:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

## Teardown Infrastructure

When done with benchmarking:

```bash
# On the instance, stop all services
./scripts/teardown.sh all

# On your local machine, destroy GCP resources
cd terraform
terraform destroy
```

## Troubleshooting

**Models not loading:**
- Check HF_TOKEN is correct in .env files
- Verify HuggingFace account has access to gated models
- Check disk space: `df -h`

**Out of memory:**
- Reduce `--gpu-memory-utilization` in docker-compose.yml
- Ensure only one environment is running at a time

**Connection refused:**
- Wait longer for services to start
- Check Docker logs for errors
- Verify firewall rules allow traffic

**Benchmark fails:**
- Ensure Python dependencies are installed: `pip3 install -r benchmark/requirements.txt`
- Check endpoint is accessible: `curl http://localhost:8080/health`
- Verify models are loaded: `curl http://localhost:8080/v1/models`
