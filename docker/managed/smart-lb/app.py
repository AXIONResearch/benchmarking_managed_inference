import asyncio
import os
import logging
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Load Balancer")

# Configuration
VLLM_ENDPOINTS = os.getenv("VLLM_ENDPOINTS", "").split(",")
METRICS_POLL_INTERVAL = int(os.getenv("METRICS_POLL_INTERVAL", "1"))

# Endpoint metrics cache
endpoint_metrics: Dict[str, Dict] = {}


class EndpointSelector:
    """Selects the best endpoint based on queue depth and response time."""

    def __init__(self, endpoints: List[str]):
        self.endpoints = endpoints

    async def get_best_endpoint(self, model: Optional[str] = None) -> str:
        """
        Select endpoint with lowest queue depth.
        If model is specified, route to the least busy replica of that model.
        """
        if model:
            # Map models to their replica endpoints
            model_endpoints = {
                "meta-llama/Llama-3.1-8B-Instruct": [self.endpoints[0], self.endpoints[1]],
                "Qwen/Qwen2.5-7B-Instruct": [self.endpoints[2], self.endpoints[3]],
                "meta-llama/Llama-3.3-70B-Instruct": [self.endpoints[4], self.endpoints[5]],
            }

            # Get endpoints for the requested model
            candidates = model_endpoints.get(model, self.endpoints[:2])

            # Find the least busy replica
            min_queue_depth = float('inf')
            best_endpoint = candidates[0]

            for endpoint in candidates:
                metrics = endpoint_metrics.get(endpoint, {})
                queue_depth = metrics.get("queue_depth", float('inf'))

                if queue_depth < min_queue_depth:
                    min_queue_depth = queue_depth
                    best_endpoint = endpoint

            logger.info(f"Model {model}: Selected {best_endpoint} (queue: {min_queue_depth})")
            return best_endpoint

        # If no model specified, find endpoint with lowest queue depth across all
        min_queue_depth = float('inf')
        best_endpoint = self.endpoints[0]

        for endpoint in self.endpoints:
            metrics = endpoint_metrics.get(endpoint, {})
            queue_depth = metrics.get("queue_depth", float('inf'))

            if queue_depth < min_queue_depth:
                min_queue_depth = queue_depth
                best_endpoint = endpoint

        logger.info(f"Selected endpoint: {best_endpoint} (queue depth: {min_queue_depth})")
        return best_endpoint


selector = EndpointSelector(VLLM_ENDPOINTS)


async def fetch_endpoint_metrics(endpoint: str) -> Dict:
    """Fetch metrics from a vLLM endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{endpoint}/metrics")
            if response.status_code == 200:
                # Parse Prometheus metrics
                metrics_text = response.text
                queue_depth = 0

                # Extract queue depth from metrics
                for line in metrics_text.split('\n'):
                    if 'vllm:num_requests_waiting' in line and not line.startswith('#'):
                        try:
                            queue_depth = float(line.split()[-1])
                        except (ValueError, IndexError):
                            pass

                return {
                    "endpoint": endpoint,
                    "queue_depth": queue_depth,
                    "timestamp": time.time(),
                    "healthy": True
                }
    except Exception as e:
        logger.error(f"Failed to fetch metrics from {endpoint}: {e}")

    return {
        "endpoint": endpoint,
        "queue_depth": float('inf'),
        "timestamp": time.time(),
        "healthy": False
    }


async def metrics_poller():
    """Background task to poll metrics from all endpoints."""
    while True:
        try:
            tasks = [fetch_endpoint_metrics(endpoint) for endpoint in VLLM_ENDPOINTS]
            results = await asyncio.gather(*tasks)

            for metrics in results:
                endpoint_metrics[metrics["endpoint"]] = metrics

            logger.debug(f"Updated metrics: {endpoint_metrics}")
        except Exception as e:
            logger.error(f"Error in metrics poller: {e}")

        await asyncio.sleep(METRICS_POLL_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """Start background metrics polling."""
    asyncio.create_task(metrics_poller())
    logger.info(f"Smart LB started with endpoints: {VLLM_ENDPOINTS}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    healthy_count = sum(1 for m in endpoint_metrics.values() if m.get("healthy", False))
    return {
        "status": "healthy" if healthy_count > 0 else "unhealthy",
        "endpoints": len(VLLM_ENDPOINTS),
        "healthy_endpoints": healthy_count
    }


@app.get("/metrics")
async def metrics():
    """Expose aggregated metrics."""
    return endpoint_metrics


@app.post("/v1/completions")
@app.post("/v1/chat/completions")
async def proxy_request(request: Request):
    """Proxy requests to the best available endpoint."""
    try:
        # Parse request body
        body = await request.json()
        model = body.get("model")

        # Select best endpoint
        endpoint = await selector.get_best_endpoint(model)

        # Forward request
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{endpoint}{request.url.path}",
                json=body,
                headers=dict(request.headers)
            )

            # Handle streaming responses
            if body.get("stream", False):
                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_response(),
                    media_type=response.headers.get("content-type"),
                    status_code=response.status_code
                )
            else:
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code
                )

    except Exception as e:
        logger.error(f"Error proxying request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List all available models across endpoints."""
    models = [
        {"id": "meta-llama/Llama-3.1-8B-Instruct", "object": "model", "replicas": 2},
        {"id": "Qwen/Qwen2.5-7B-Instruct", "object": "model", "replicas": 2},
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "replicas": 2},
    ]
    return {"object": "list", "data": models}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
