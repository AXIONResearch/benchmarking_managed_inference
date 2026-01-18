#!/bin/bash
set -e

exec > >(tee /var/log/kvcached-startup.log)
exec 2>&1

echo "========================================="
echo "KVCached Deployment Starting"
echo "========================================="
date

# Install dependencies
apt-get update
apt-get install -y curl wget git jq python3-pip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Clone repository
cd /root
git clone https://github.com/AXIONResearch/benchmarking_managed_inference.git
cd benchmarking_managed_inference
git checkout kvcached

# Configure environment
cat > docker/managed/.env <<EOF
HF_TOKEN=${HF_TOKEN}
EOF

# Copy T4 configurations
cp docker/managed/smart-lb/app.t4.py docker/managed/smart-lb/app.py

# Pull images
cd docker/managed
docker-compose -f docker-compose.t4.yml pull

# Start services
docker-compose -f docker-compose.t4.yml up -d

# Install Python dependencies
pip3 install aiohttp numpy pandas matplotlib

echo "========================================="
echo "KVCached Deployment Complete"
echo "========================================="
nvidia-smi
date
