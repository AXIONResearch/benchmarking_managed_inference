# Deploy KVCached - One Command

## Step 1: Add Your HuggingFace Token

```bash
cd terraform
nano terraform.tfvars
```

Change line 10:
```
hf_token = "YOUR_HF_TOKEN_HERE"
```

to:
```
hf_token = "hf_your_actual_token"
```

Get token from: https://huggingface.co/settings/tokens

Save and exit.

## Step 2: Deploy

```bash
terraform init
terraform apply
```

Type `yes` when prompted.

**Wait 15-20 minutes** for complete deployment.

## Step 3: Verify

```bash
# Get outputs
terraform output

# SSH to VM
$(terraform output -raw ssh_command)

# Check startup progress
sudo tail -f /var/log/kvcached-startup.log

# When complete, test health
curl http://localhost:8081/health
```

## Done

Access externally:
```bash
curl http://$(terraform output -raw instance_ip):8081/health
```

Destroy when done:
```bash
terraform destroy
```
