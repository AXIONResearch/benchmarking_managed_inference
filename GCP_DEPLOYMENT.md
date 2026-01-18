# GCP Deployment Guide

Step-by-step guide to deploy the benchmark infrastructure on GCP with 6x H100 GPUs.

## Prerequisites

1. **GCP Account** with billing enabled
2. **GCP Project** created
3. **gcloud CLI** installed and authenticated
4. **Terraform** installed (v1.0+)
5. **SSH key pair** generated

## Step 1: Set Up GCP Authentication

```bash
# Authenticate with GCP
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
```

## Step 2: Configure Terraform

```bash
# Navigate to terraform directory
cd terraform

# Copy the example tfvars
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
nano terraform.tfvars
```

Edit `terraform.tfvars` with your settings:

```hcl
project_id           = "your-gcp-project-id"
region              = "us-central1"
zone                = "us-central1-a"  # Must have H100 availability
ssh_user            = "ubuntu"
ssh_public_key_path = "~/.ssh/id_rsa.pub"
```

**Important:** Check H100 availability in your region:
- `us-central1-a` (Iowa)
- `us-east4-a` (Virginia)
- `europe-west4-a` (Netherlands)

Verify with:
```bash
gcloud compute accelerator-types list --filter="name:nvidia-h100-80gb"
```

## Step 3: Deploy Infrastructure with Terraform

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy (this will create a ~$30-40/hour instance)
terraform apply

# Save the instance IP
INSTANCE_IP=$(terraform output -raw instance_ip)
echo "Instance IP: $INSTANCE_IP"

# Save this IP for later
echo $INSTANCE_IP > ../instance_ip.txt
```

**Cost Warning:** The a3-highgpu-8g instance costs approximately **$30-40 per hour**. Remember to destroy it when done!

## Step 4: Wait for Startup Script

The instance runs a startup script that installs:
- Docker & Docker Compose
- NVIDIA Container Toolkit
- CUDA 12.4 drivers

This takes approximately **10-15 minutes**.

Monitor progress:

```bash
# SSH into the instance
ssh ubuntu@$INSTANCE_IP

# Watch startup script progress
sudo tail -f /var/log/syslog | grep startup-script

# Or check if Docker is ready
docker --version
nvidia-smi
```

Press `Ctrl+C` when you see "Setup complete! Ready for vLLM deployment."

## Step 5: Upload Project to Instance

From your local machine:

```bash
# Get the instance IP if you don't have it
cd terraform
INSTANCE_IP=$(terraform output -raw instance_ip)
cd ..

# Copy the entire project to the instance
rsync -avz --exclude '.git' --exclude 'results' \
  ./ ubuntu@$INSTANCE_IP:~/benchmarking_managed_inference/

# SSH into the instance
ssh ubuntu@$INSTANCE_IP
cd benchmarking_managed_inference
```

## Step 6: Verify GPU Setup

```bash
# Check GPUs are available
nvidia-smi

# Should show 6-8 H100 80GB GPUs
# We'll use GPUs 0-5 (6 GPUs total)
```

Expected output:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.xxx      Driver Version: 535.xxx      CUDA Version: 12.4   |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA H100 80GB    Off  | 00000000:00:04.0 Off |                    0 |
| N/A   30C    P0    70W / 700W |      0MiB / 81559MiB |      0%      Default |
|   1  NVIDIA H100 80GB    Off  | 00000000:00:05.0 Off |                    0 |
...
```

## Step 7: Deploy Baseline Environment

```bash
# Make scripts executable (if not already)
chmod +x scripts/*.sh
chmod +x benchmark/*.sh

# Deploy baseline
./scripts/deploy.sh baseline
```

This will:
1. Pull vLLM Docker images (~10-15 minutes)
2. Start 6 vLLM pods (one per GPU)
3. Download models from HuggingFace (first run takes 20-30 minutes)
4. Build and start the load balancer

**Model Download Sizes:**
- Llama 3.1 8B: ~16 GB (x2 replicas = shared cache)
- Qwen 2.5 7B: ~14 GB (x2 replicas = shared cache)
- Llama 3.3 70B AWQ: ~40 GB (x2 replicas = shared cache)
- **Total first download: ~70 GB**

Models are cached in `~/.cache/huggingface` and shared across replicas.

## Step 8: Monitor Deployment

In separate terminal windows:

```bash
# Terminal 1: Watch overall docker status
watch -n 2 docker ps

# Terminal 2: Watch GPU utilization
watch -n 1 nvidia-smi

# Terminal 3: Follow load balancer logs
docker logs -f baseline-simple-lb

# Terminal 4: Follow a vLLM pod
docker logs -f vllm-llama-8b-1
```

Wait for all pods to show "Uvicorn running on" and load models into memory.

## Step 9: Test Deployment

```bash
# Quick health check
curl http://localhost:8080/health

# List available models
curl http://localhost:8080/v1/models

# Test inference
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "Hello! Say hi in 5 words."}],
    "max_tokens": 20
  }'

# Run comprehensive test
./scripts/test_baseline.sh
```

## Step 10: Run Benchmarks

```bash
# Install GenAI-Perf (if not already installed)
pip3 install genai-perf

# Benchmark all models
./scripts/benchmark_all_models.sh baseline 10 100

# Or benchmark individually
./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.1-8B-Instruct" 20 200
./benchmark/genai_perf_runner.sh baseline "Qwen/Qwen2.5-7B-Instruct" 20 200
./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.3-70B-Instruct" 20 200
```

Results will be saved to `results/baseline/genai_perf_*/`

## Step 11: Deploy Managed Environment (Optional)

Once baseline benchmarks are complete:

```bash
# Teardown baseline
./scripts/teardown.sh baseline

# Deploy managed
./scripts/deploy.sh managed

# Test managed
curl http://localhost:8081/health

# Benchmark managed
./scripts/benchmark_all_models.sh managed 10 100
```

## Step 12: Download Results

From your local machine:

```bash
# Download results from instance
rsync -avz ubuntu@$INSTANCE_IP:~/benchmarking_managed_inference/results/ ./results/

# Analyze results
python3 analysis/compare.py
```

## Step 13: Cleanup and Destroy

**IMPORTANT:** Don't forget to destroy the instance to avoid charges!

```bash
# On the instance, stop all services
./scripts/teardown.sh all

# Exit SSH
exit

# On your local machine, destroy infrastructure
cd terraform
terraform destroy

# Confirm with 'yes'
```

This will delete the expensive H100 instance and stop billing.

## Troubleshooting

### Models Not Downloading

```bash
# Check HF token is set
cat docker/baseline/.env

# Test HuggingFace authentication
docker run --rm -e HF_TOKEN=$HF_TOKEN \
  huggingface/transformers-pytorch-gpu \
  huggingface-cli whoami
```

### Out of Memory

```bash
# Reduce GPU memory utilization
# Edit docker/baseline/docker-compose.yml
# Change --gpu-memory-utilization from 0.95 to 0.90 or 0.85
```

### Pod Failing to Start

```bash
# Check logs
docker logs vllm-llama-8b-1

# Common issues:
# - Model still downloading (wait)
# - OOM (reduce gpu-memory-utilization)
# - Wrong model name (check HF path)
```

### Can't Access from Browser

The instance is accessible via SSH only by default. To access from browser:

```bash
# SSH tunnel from local machine
ssh -L 8080:localhost:8080 ubuntu@$INSTANCE_IP

# Now access http://localhost:8080 in your browser
```

## Cost Optimization

- **Use Spot Instances:** Edit `terraform/main.tf` to add `preemptible = true`
- **Use Smaller GPUs for Testing:** Replace H100 with A100 or T4 in terraform
- **Limit Benchmark Duration:** Use fewer requests in benchmarks
- **Share Instance:** Run both baseline and managed tests on same instance

## Estimated Costs

- **a3-highgpu-8g (8x H100):** ~$35/hour
- **Full benchmark run (both baseline + managed):** ~3-4 hours
- **Total cost for complete testing:** ~$120-140

To minimize costs:
- Deploy instance right before testing
- Destroy immediately after downloading results
- Use spot/preemptible instances (50-70% cheaper but can be interrupted)
