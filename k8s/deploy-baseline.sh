#!/bin/bash
set -e

echo "=== Deploying baseline vLLM to Kubernetes ==="

# Check if k3s is installed
if ! command -v kubectl &> /dev/null; then
    echo "Installing k3s (lightweight Kubernetes)..."
    curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

    # Wait for k3s to be ready
    echo "Waiting for k3s to be ready..."
    sleep 10
    sudo k3s kubectl wait --for=condition=Ready node --all --timeout=60s

    # Set up kubectl alias
    echo "alias kubectl='sudo k3s kubectl'" >> ~/.bashrc
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi

# Use k3s kubectl
KUBECTL="sudo k3s kubectl"

# Check if HF_TOKEN is set
if [ -z "$HF_TOKEN" ]; then
    echo "Error: HF_TOKEN environment variable not set"
    echo "Usage: HF_TOKEN=your_token ./deploy-baseline.sh"
    exit 1
fi

# Create namespace
echo "Creating baseline namespace..."
$KUBECTL apply -f baseline/namespace.yaml

# Create HuggingFace token secret
echo "Creating HuggingFace token secret..."
$KUBECTL create secret generic huggingface-token \
    --from-literal=token="$HF_TOKEN" \
    --namespace=baseline \
    --dry-run=client -o yaml | $KUBECTL apply -f -

# Deploy vLLM services
echo "Deploying vLLM pods..."
$KUBECTL apply -f baseline/llama-8b-deployment.yaml
$KUBECTL apply -f baseline/qwen-7b-deployment.yaml
$KUBECTL apply -f baseline/mistral-7b-deployment.yaml

# Wait for pods to be ready
echo ""
echo "Waiting for pods to be ready (this may take several minutes)..."
$KUBECTL wait --for=condition=Ready pod \
    -l app=vllm \
    --namespace=baseline \
    --timeout=600s || true

# Show status
echo ""
echo "=== Deployment Status ==="
$KUBECTL get pods -n baseline -o wide
echo ""
$KUBECTL get svc -n baseline

echo ""
echo "=== Services ==="
echo "Llama-8B:  vllm-llama-8b.baseline.svc.cluster.local:8000"
echo "Qwen-7B:   vllm-qwen-7b.baseline.svc.cluster.local:8000"
echo "Mistral-7B: vllm-mistral-7b.baseline.svc.cluster.local:8000"
echo ""
echo "kube-proxy will automatically load balance across replicas!"
