"""
vLLM Benchmark Client

Handles async requests to vLLM endpoints and measures performance metrics.
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)


class VLLMBenchmarkClient:
    def __init__(self, endpoint: str, timeout: int = 300):
        self.endpoint = endpoint.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def run_benchmark(
        self,
        requests: List[Dict],
        concurrency: int = 10
    ) -> List[Dict]:
        """Run benchmark with specified concurrency."""
        semaphore = asyncio.Semaphore(concurrency)
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            tasks = [
                self._send_request_with_semaphore(session, req, semaphore)
                for req in requests
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Request {i} failed: {result}")
                processed_results.append({
                    'error': str(result),
                    'request_id': i
                })
            else:
                processed_results.append(result)

        return processed_results

    async def _send_request_with_semaphore(
        self,
        session: aiohttp.ClientSession,
        request: Dict,
        semaphore: asyncio.Semaphore
    ) -> Dict:
        """Send a single request with semaphore control."""
        async with semaphore:
            return await self._send_request(session, request)

    async def _send_request(
        self,
        session: aiohttp.ClientSession,
        request: Dict
    ) -> Dict:
        """Send a single request and measure metrics."""
        url = f"{self.endpoint}/v1/chat/completions"

        payload = {
            "model": request.get("model"),
            "messages": request.get("messages"),
            "max_tokens": request.get("max_tokens", 512),
            "temperature": request.get("temperature", 0.7),
            "stream": False
        }

        start_time = time.time()
        ttft = None
        tokens_generated = 0
        prompt_tokens = 0

        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        'error': f"HTTP {response.status}: {error_text}",
                        'latency': time.time() - start_time
                    }

                # For non-streaming, TTFT is the same as latency
                result = await response.json()
                end_time = time.time()

                ttft = end_time - start_time
                latency = ttft

                # Extract token counts
                usage = result.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)

                return {
                    'ttft': ttft,
                    'latency': latency,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'throughput': completion_tokens / latency if latency > 0 else 0,
                    'model': request.get('model'),
                    'max_tokens': request.get('max_tokens'),
                }

        except asyncio.TimeoutError:
            return {
                'error': 'Request timeout',
                'latency': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {
                'error': str(e),
                'latency': time.time() - start_time
            }


    async def get_models(self) -> List[str]:
        """Get list of available models."""
        url = f"{self.endpoint}/v1/models"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [model['id'] for model in data.get('data', [])]
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
        return []

    async def health_check(self) -> bool:
        """Check if endpoint is healthy."""
        url = f"{self.endpoint}/health"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
