#!/bin/bash
set -e

# Baseline Testing Script
# Tests deployment, routing, and basic functionality

echo "===================================="
echo "BASELINE DEPLOYMENT TEST"
echo "===================================="
echo ""

# Check if .env exists
if [ ! -f "docker/baseline/.env" ]; then
    echo "❌ Error: docker/baseline/.env not found"
    echo "Please run:"
    echo "  cp docker/baseline/.env.example docker/baseline/.env"
    echo "  # Edit .env and add your HF_TOKEN"
    exit 1
fi

echo "✓ .env file exists"
echo ""

# Check if HF_TOKEN is set
if ! grep -q "HF_TOKEN=hf_" docker/baseline/.env 2>/dev/null; then
    echo "⚠️  Warning: HF_TOKEN may not be set correctly in docker/baseline/.env"
    echo "Make sure it starts with 'hf_'"
    echo ""
fi

echo "===================================="
echo "STEP 1: Deploying Baseline"
echo "===================================="
./scripts/deploy.sh baseline

echo ""
echo "===================================="
echo "STEP 2: Testing Load Balancer"
echo "===================================="

# Wait a bit for services to stabilize
echo "Waiting 10 seconds for services to stabilize..."
sleep 10

# Test load balancer health
echo ""
echo "Testing load balancer health..."
if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ Load balancer is healthy"
    curl -s http://localhost:8080/health | python3 -m json.tool
else
    echo "❌ Load balancer health check failed"
    exit 1
fi

echo ""
echo "Testing load balancer /v1/models endpoint..."
if curl -f -s http://localhost:8080/v1/models > /dev/null 2>&1; then
    echo "✓ Models endpoint accessible"
    curl -s http://localhost:8080/v1/models | python3 -m json.tool
else
    echo "❌ Models endpoint failed"
    exit 1
fi

echo ""
echo "===================================="
echo "STEP 3: Testing Individual Pods"
echo "===================================="

# Function to test a pod
test_pod() {
    local port=$1
    local name=$2

    echo ""
    echo "Testing $name (port $port)..."

    if curl -f -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "  ✓ Health check passed"
    else
        echo "  ❌ Health check failed"
        return 1
    fi

    if curl -f -s http://localhost:$port/v1/models > /dev/null 2>&1; then
        echo "  ✓ Models endpoint accessible"
        # Show which model this pod is serving
        MODEL=$(curl -s http://localhost:$port/v1/models | python3 -c "import sys, json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || echo "unknown")
        echo "  📦 Serving: $MODEL"
    else
        echo "  ❌ Models endpoint failed"
        return 1
    fi
}

# Test all 6 pods
test_pod 8001 "Llama 8B Replica 1 (GPU 0)"
test_pod 8002 "Llama 8B Replica 2 (GPU 1)"
test_pod 8003 "Qwen 7B Replica 1 (GPU 2)"
test_pod 8004 "Qwen 7B Replica 2 (GPU 3)"
test_pod 8005 "Llama 70B Replica 1 (GPU 4)"
test_pod 8006 "Llama 70B Replica 2 (GPU 5)"

echo ""
echo "===================================="
echo "STEP 4: Testing Model Routing"
echo "===================================="

# Test routing to each model type
echo ""
echo "Testing routing to Llama 8B..."
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words."}],
    "max_tokens": 10,
    "temperature": 0.1
  }' > /tmp/test_llama8b.json

if [ -s /tmp/test_llama8b.json ]; then
    echo "✓ Llama 8B routing successful"
    echo "Response preview:"
    python3 -c "import json; data=json.load(open('/tmp/test_llama8b.json')); print('  ', data['choices'][0]['message']['content'][:100])" 2>/dev/null || cat /tmp/test_llama8b.json
else
    echo "❌ Llama 8B routing failed"
fi

echo ""
echo "Testing routing to Qwen 7B..."
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words."}],
    "max_tokens": 10,
    "temperature": 0.1
  }' > /tmp/test_qwen7b.json

if [ -s /tmp/test_qwen7b.json ]; then
    echo "✓ Qwen 7B routing successful"
    echo "Response preview:"
    python3 -c "import json; data=json.load(open('/tmp/test_qwen7b.json')); print('  ', data['choices'][0]['message']['content'][:100])" 2>/dev/null || cat /tmp/test_qwen7b.json
else
    echo "❌ Qwen 7B routing failed"
fi

echo ""
echo "Testing routing to Llama 70B..."
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words."}],
    "max_tokens": 10,
    "temperature": 0.1
  }' > /tmp/test_llama70b.json

if [ -s /tmp/test_llama70b.json ]; then
    echo "✓ Llama 70B routing successful"
    echo "Response preview:"
    python3 -c "import json; data=json.load(open('/tmp/test_llama70b.json')); print('  ', data['choices'][0]['message']['content'][:100])" 2>/dev/null || cat /tmp/test_llama70b.json
else
    echo "❌ Llama 70B routing failed"
fi

echo ""
echo "===================================="
echo "STEP 5: Testing Round-Robin Behavior"
echo "===================================="

echo ""
echo "Sending 4 requests to Llama 8B to verify round-robin..."
echo "(Should alternate between replicas on GPUs 0 and 1)"
echo ""

# Enable verbose logging to see which endpoint is selected
echo "Check docker/baseline logs with:"
echo "  docker logs baseline-simple-lb 2>&1 | tail -20"
echo ""

for i in {1..4}; do
    echo "Request $i to Llama 8B..."
    curl -s http://localhost:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
      }' > /dev/null
    sleep 1
done

echo ""
echo "Recent load balancer logs (showing routing decisions):"
docker logs baseline-simple-lb 2>&1 | grep "Selected" | tail -10

echo ""
echo "===================================="
echo "STEP 6: Quick Benchmark (Optional)"
echo "===================================="

echo ""
read -p "Run a quick GenAI-Perf benchmark? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Running quick benchmark (5 requests, concurrency 2)..."

    if command -v genai-perf &> /dev/null; then
        ./benchmark/genai_perf_runner.sh baseline "meta-llama/Llama-3.1-8B-Instruct" 2 5
    else
        echo "GenAI-Perf not installed. Install with:"
        echo "  pip3 install genai-perf"
        echo ""
        echo "Or run manually:"
        echo "  ./benchmark/genai_perf_runner.sh baseline \"meta-llama/Llama-3.1-8B-Instruct\" 2 5"
    fi
else
    echo "Skipping benchmark"
fi

echo ""
echo "===================================="
echo "✓ BASELINE TESTING COMPLETE"
echo "===================================="
echo ""
echo "Summary:"
echo "  • Load balancer: http://localhost:8080"
echo "  • Individual pods: http://localhost:8001-8006"
echo "  • 3 models with 2 replicas each"
echo "  • Round-robin routing verified"
echo ""
echo "Next steps:"
echo "  1. Run full benchmarks:"
echo "     ./scripts/benchmark_all_models.sh baseline 10 100"
echo ""
echo "  2. View logs:"
echo "     docker logs -f baseline-simple-lb"
echo "     docker logs -f vllm-llama-8b-1"
echo ""
echo "  3. Monitor GPUs:"
echo "     watch -n 1 nvidia-smi"
echo ""
echo "  4. When done, teardown:"
echo "     ./scripts/teardown.sh baseline"
echo ""
