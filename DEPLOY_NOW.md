# Deploy KVCached RIGHT NOW - Simple Steps

Your VM already exists. Here's how to deploy everything:

## Option 1: Run Setup Script on VM (RECOMMENDED)

### Step 1: Connect to VM
```bash
gcloud compute ssh --zone "us-central1-a" "omri-kvcached" --project "robotic-tide-459208-h4"
```

### Step 2: Run the Full Setup (Run this entire block)
```bash
curl -fsSL https://raw.githubusercontent.com/AXIONResearch/benchmarking_managed_inference/kvcached/terraform/startup.sh | sudo bash
```

This installs everything automatically: Docker, NVIDIA Toolkit, clones repo, etc.

**Wait 10-15 minutes** for it to complete.

### Step 3: Activate Docker Group
```bash
newgrp docker
cd ~/benchmarking_managed_inference
```

### Step 4: Set HuggingFace Token
```bash
nano docker/managed/.env
```
Change `your_huggingface_token_here` to your token.
Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 5: Deploy KVCached
```bash
cp docker/managed/smart-lb/app.t4.py docker/managed/smart-lb/app.py
cd docker/managed
docker-compose -f docker-compose.t4.yml up -d
```

### Step 6: Verify (Wait 5-10 min for models to load)
```bash
# Check health
curl http://localhost:8081/health

# Test
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"Hi"}],"max_tokens":20}' | jq
```

---

## Option 2: Manual Setup (If Option 1 Fails)

### On the VM:
```bash
# Remove bad nvidia repo
sudo rm -f /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update
sudo apt-get update

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Activate docker group
newgrp docker

# Deploy
cd ~/benchmarking_managed_inference
nano docker/managed/.env  # Add your HF token
cp docker/managed/smart-lb/app.t4.py docker/managed/smart-lb/app.py
cd docker/managed
docker-compose -f docker-compose.t4.yml up -d
```

---

## Quick Monitor Commands

```bash
# GPU usage
nvidia-smi

# Container status
docker ps

# Logs
docker logs -f vllm-llama-8b-kvcached

# Health
curl http://localhost:8081/health

# From your local machine
curl http://146.148.60.185:8081/health
```

---

## That's It!

No more complicated scripts. Just:
1. Connect
2. Run setup
3. Add HF token
4. Deploy
5. Verify
