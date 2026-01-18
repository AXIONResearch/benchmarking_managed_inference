# Deploy KVCached - One Command

## Step 1: Add Your HuggingFace Token

```bash
cd terraform
nano terraform.tfvars
```

Change:
```
hf_token = "YOUR_HF_TOKEN_HERE"
```

to:
```
hf_token = "hf_your_actual_token"
```

Get token: https://huggingface.co/settings/tokens

Save and exit.

## Step 2: Deploy

```bash
terraform apply
```

Type `yes` when prompted.

**Terraform will:**
- Use existing `omri-kvcached` VM if it exists
- OR create new VM if it doesn't exist
- SSH in and deploy KVCached automatically

**Wait 10-15 minutes** for deployment.

## Step 3: Verify

```bash
# Get outputs
terraform output

# SSH to VM
$(terraform output -raw ssh_command)

# Check deployment log
sudo tail -f /var/log/kvcached-deploy.log

# Test health
curl http://localhost:8081/health
```

## External Access

```bash
curl http://$(terraform output -raw instance_ip):8081/health
```

## Cleanup

```bash
terraform destroy
```
