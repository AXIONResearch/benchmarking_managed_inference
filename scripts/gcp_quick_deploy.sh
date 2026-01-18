#!/bin/bash
set -e

# GCP Quick Deploy Script
# Automates terraform deployment and project upload

echo "===================================="
echo "GCP H100 Instance Quick Deploy"
echo "===================================="
echo ""

# Check if we're in the right directory
if [ ! -f "terraform/main.tf" ]; then
    echo "❌ Error: Must run from project root"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo "✓ gcloud CLI found"

if ! command -v terraform &> /dev/null; then
    echo "❌ terraform not found. Install from: https://www.terraform.io/downloads"
    exit 1
fi
echo "✓ terraform found"

if [ ! -f "terraform/terraform.tfvars" ]; then
    echo ""
    echo "❌ terraform.tfvars not found"
    echo ""
    echo "Please create it:"
    echo "  cd terraform"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    echo "  nano terraform.tfvars  # Edit with your GCP project ID"
    echo ""
    exit 1
fi
echo "✓ terraform.tfvars found"

if [ ! -f "docker/baseline/.env" ]; then
    echo "❌ docker/baseline/.env not found"
    echo "But we have your HF token, so this should exist already!"
    exit 1
fi
echo "✓ HuggingFace token configured"

echo ""
echo "===================================="
echo "Step 1: Deploy GCP Infrastructure"
echo "===================================="
echo ""

cd terraform

# Initialize terraform if needed
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

echo ""
echo "⚠️  WARNING: This will create an ~$35/hour H100 instance!"
echo ""
read -p "Continue with deployment? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "Running terraform apply..."
terraform apply -auto-approve

# Get instance IP
INSTANCE_IP=$(terraform output -raw instance_ip)
echo ""
echo "✓ Instance created: $INSTANCE_IP"
echo $INSTANCE_IP > ../instance_ip.txt
echo "  (Saved to instance_ip.txt)"

cd ..

echo ""
echo "===================================="
echo "Step 2: Wait for Startup Script"
echo "===================================="
echo ""
echo "The instance is installing Docker, NVIDIA drivers, and CUDA."
echo "This takes approximately 10-15 minutes."
echo ""
echo "Checking instance readiness..."

# Wait for SSH to be available
echo "Waiting for SSH to be ready..."
for i in {1..30}; do
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "echo SSH ready" 2>/dev/null; then
        echo "✓ SSH is ready"
        break
    fi
    echo "  Attempt $i/30: Waiting for SSH..."
    sleep 10
done

# Wait for Docker to be ready
echo ""
echo "Waiting for Docker installation..."
for i in {1..60}; do
    if ssh ubuntu@$INSTANCE_IP "command -v docker &> /dev/null" 2>/dev/null; then
        echo "✓ Docker is installed"
        break
    fi
    echo "  Attempt $i/60: Waiting for Docker..."
    sleep 10
done

# Wait for NVIDIA drivers
echo ""
echo "Waiting for NVIDIA drivers..."
for i in {1..60}; do
    if ssh ubuntu@$INSTANCE_IP "command -v nvidia-smi &> /dev/null" 2>/dev/null; then
        echo "✓ NVIDIA drivers installed"
        break
    fi
    echo "  Attempt $i/60: Waiting for NVIDIA drivers..."
    sleep 10
done

echo ""
echo "===================================="
echo "Step 3: Upload Project Files"
echo "===================================="
echo ""

echo "Uploading project to instance..."
rsync -avz --progress \
  --exclude '.git' \
  --exclude 'results' \
  --exclude 'terraform/.terraform' \
  --exclude '*.tfstate*' \
  ./ ubuntu@$INSTANCE_IP:~/benchmarking_managed_inference/

echo "✓ Project uploaded"

echo ""
echo "===================================="
echo "Step 4: Verify GPU Setup"
echo "===================================="
echo ""

echo "Checking GPUs on instance..."
ssh ubuntu@$INSTANCE_IP "nvidia-smi --query-gpu=name,memory.total --format=csv"

echo ""
echo "===================================="
echo "✓ GCP DEPLOYMENT COMPLETE"
echo "===================================="
echo ""
echo "Instance IP: $INSTANCE_IP"
echo ""
echo "Next steps:"
echo ""
echo "1. SSH into instance:"
echo "   ssh ubuntu@$INSTANCE_IP"
echo ""
echo "2. Navigate to project:"
echo "   cd benchmarking_managed_inference"
echo ""
echo "3. Deploy baseline:"
echo "   ./scripts/deploy.sh baseline"
echo ""
echo "4. Or run the full test:"
echo "   ./scripts/test_baseline.sh"
echo ""
echo "5. When done, teardown from local machine:"
echo "   cd terraform && terraform destroy"
echo ""
echo "⚠️  REMINDER: Instance costs ~$35/hour - destroy when done!"
echo ""
