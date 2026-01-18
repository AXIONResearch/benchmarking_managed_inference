#!/bin/bash
set -e

exec > >(tee /var/log/startup-script.log)
exec 2>&1

echo "============================================"
echo "KVCached VM Startup Script"
echo "============================================"
date

# Update system
apt-get update
apt-get upgrade -y

# Install basic utilities
apt-get install -y curl wget git htop jq python3-pip

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    DOCKER_COMPOSE_VERSION="2.24.0"
    curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Install NVIDIA Container Toolkit (Debian 12 compatible)
echo "Installing NVIDIA Container Toolkit..."
rm -f /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Add GPG key
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Add repository
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update
apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Add default user to docker group
usermod -aG docker omrifainaro || true

# Clone repository to user's home
cd /home/omrifainaro
if [ ! -d "benchmarking_managed_inference" ]; then
    sudo -u omrifainaro git clone https://github.com/AXIONResearch/benchmarking_managed_inference.git
    cd benchmarking_managed_inference
    sudo -u omrifainaro git checkout kvcached
fi

# Set up .env file
cd /home/omrifainaro/benchmarking_managed_inference
if [ ! -f "docker/managed/.env" ]; then
    sudo -u omrifainaro cp docker/managed/.env.example docker/managed/.env
fi

# Install Python dependencies
pip3 install aiohttp numpy pandas matplotlib

# Test GPU access
nvidia-smi

echo "============================================"
echo "Startup script complete!"
echo "============================================"
date
