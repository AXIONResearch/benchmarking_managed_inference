# KVCached Benchmarking on GCP

Deploy KVCached vLLM with one Terraform command.

## Prerequisites

- GCP account with billing enabled
- HuggingFace token: https://huggingface.co/settings/tokens
- Terraform installed
- gcloud CLI authenticated: `gcloud auth application-default login`

## Deploy

1. **Edit terraform.tfvars**:
```bash
cd terraform
nano terraform.tfvars
```

Add your HuggingFace token:
```hcl
hf_token = "hf_your_actual_token_here"
```

2. **Deploy everything**:
```bash
terraform init
terraform apply
```

Type `yes` when prompted.

**Wait 15-20 minutes** for:
- VM creation
- Docker installation
- NVIDIA Container Toolkit setup
- Model downloads (~20GB)
- Services startup

3. **Get connection info**:
```bash
terraform output
```

## Verify Deployment

```bash
# SSH into VM
$(terraform output -raw ssh_command)

# Check startup progress
sudo tail -f /var/log/kvcached-startup.log

# Check health (once startup complete)
curl http://localhost:8081/health

# Test inference
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"Hello"}],"max_tokens":20}'
```

## Architecture

- **4x Tesla T4 GPUs** (16GB each)
- **4 Models**: Llama 8B, Qwen 7B, Mistral 7B, Gemma 9B
- **KVCached**: Elastic KV cache via CUDA VMM
- **Smart Load Balancer**: Queue-aware routing (port 8081)

## Monitoring

```bash
# GPU usage
nvidia-smi

# Container status
docker ps

# Logs
docker logs -f vllm-llama-8b-kvcached
```

## Cleanup

```bash
terraform destroy
```

## External Access

Once deployed, access from anywhere:
```bash
curl http://$(terraform output -raw instance_ip):8081/health
```
