#!/bin/bash
set -e

# ModelsGuard Deployment Script
# Usage: ./scripts/deploy.sh [baseline|managed]

ENV=$1

if [ -z "$ENV" ]; then
    echo "Usage: ./scripts/deploy.sh [baseline|managed]"
    exit 1
fi

if [ "$ENV" != "baseline" ] && [ "$ENV" != "managed" ]; then
    echo "Error: Environment must be 'baseline' or 'managed'"
    exit 1
fi

echo "===================================="
echo "Deploying $ENV environment"
echo "===================================="

# Check if .env file exists
if [ ! -f "docker/$ENV/.env" ]; then
    echo "Error: .env file not found in docker/$ENV/"
    echo "Please copy .env.example to .env and fill in your HF_TOKEN"
    exit 1
fi

# Navigate to docker directory
cd "docker/$ENV"

# Pull latest images
echo "Pulling Docker images..."
docker-compose pull

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 10

# Check health
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if [ "$ENV" = "baseline" ]; then
        HEALTH_URL="http://localhost:8080/health"
    else
        HEALTH_URL="http://localhost:8081/health"
    fi

    if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
        echo "✓ Services are healthy!"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for services... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 10
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Services failed to become healthy"
    echo "Check logs with: docker-compose -f docker/$ENV/docker-compose.yml logs"
    exit 1
fi

# Show running containers
echo ""
echo "Running containers:"
docker-compose ps

echo ""
echo "===================================="
echo "Deployment complete!"
echo "===================================="
if [ "$ENV" = "baseline" ]; then
    echo "Baseline endpoint: http://localhost:8080"
    echo "Individual pods: 8001-8005"
else
    echo "Managed endpoint: http://localhost:8081"
    echo "Individual pods: 8001-8005"
fi
echo "===================================="
