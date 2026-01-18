import os
import logging
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
from itertools import cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Simple Round-Robin Load Balancer")

# Configuration
VLLM_ENDPOINTS = os.getenv("VLLM_ENDPOINTS", "").split(",")


class RoundRobinSelector:
    """Simple round-robin selector for model replicas."""

    def __init__(self, endpoints: List[str]):
        self.endpoints = endpoints

        # Model to endpoints mapping
        self.model_endpoints = {
            "meta-llama/Llama-3.1-8B-Instruct": [endpoints[0], endpoints[1]],
            "Qwen/Qwen2.5-7B-Instruct": [endpoints[2], endpoints[3]],
            "meta-llama/Llama-3.3-70B-Instruct": [endpoints[4], endpoints[5]],
        }

        # Create round-robin iterators for each model
        self.model_iterators = {
            model: cycle(eps) for model, eps in self.model_endpoints.items()
        }

        # Fallback: round-robin across all endpoints
        self.global_iterator = cycle(endpoints)

    def get_next_endpoint(self, model: Optional[str] = None) -> str:
        """
        Get next endpoint using round-robin.
        If model is specified, cycle through that model's replicas.
        """
        if model and model in self.model_iterators:
            endpoint = next(self.model_iterators[model])
            logger.info(f"Model {model}: Selected {endpoint} (round-robin)")
            return endpoint

        # Fallback to global round-robin
        endpoint = next(self.global_iterator)
        logger.info(f"No model specified: Selected {endpoint} (global round-robin)")
        return endpoint


selector = RoundRobinSelector(VLLM_ENDPOINTS)


@app.on_event("startup")
async def startup_event():
    """Startup message."""
    logger.info(f"Simple Round-Robin LB started with endpoints: {VLLM_ENDPOINTS}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "endpoints": len(VLLM_ENDPOINTS)}


@app.post("/v1/completions")
@app.post("/v1/chat/completions")
async def proxy_request(request: Request):
    """Proxy requests using round-robin selection."""
    try:
        # Parse request body
        body = await request.json()
        model = body.get("model")

        # Select endpoint via round-robin
        endpoint = selector.get_next_endpoint(model)

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
    """List all available models."""
    models = [
        {"id": "meta-llama/Llama-3.1-8B-Instruct", "object": "model", "replicas": 2},
        {"id": "Qwen/Qwen2.5-7B-Instruct", "object": "model", "replicas": 2},
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "replicas": 2},
    ]
    return {"object": "list", "data": models}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
