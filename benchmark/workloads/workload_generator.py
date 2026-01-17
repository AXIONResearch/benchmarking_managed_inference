"""
Workload Generator

Generates synthetic workloads for benchmarking based on configuration.
"""

import random
from typing import List, Dict


class WorkloadGenerator:
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', [])
        self.prompts = config.get('prompts', [])
        self.max_tokens_range = config.get('max_tokens_range', [128, 512])
        self.temperature_range = config.get('temperature_range', [0.7, 1.0])

    def generate(self, num_requests: int) -> List[Dict]:
        """Generate workload requests."""
        requests = []

        for i in range(num_requests):
            request = self._generate_single_request(i)
            requests.append(request)

        return requests

    def _generate_single_request(self, request_id: int) -> Dict:
        """Generate a single request."""
        model = random.choice(self.models) if self.models else None
        prompt_template = random.choice(self.prompts) if self.prompts else "Hello, how are you?"

        # Generate prompt variations
        prompt = self._generate_prompt(prompt_template)

        max_tokens = random.randint(
            self.max_tokens_range[0],
            self.max_tokens_range[1]
        )

        temperature = random.uniform(
            self.temperature_range[0],
            self.temperature_range[1]
        )

        return {
            'request_id': request_id,
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': max_tokens,
            'temperature': temperature
        }

    def _generate_prompt(self, template: str) -> str:
        """Generate prompt from template with variations."""
        # Simple template variable replacement
        # You can extend this with more sophisticated generation
        variations = {
            '{topic}': random.choice([
                'artificial intelligence',
                'climate change',
                'quantum computing',
                'space exploration',
                'renewable energy',
                'biotechnology'
            ]),
            '{task}': random.choice([
                'explain',
                'summarize',
                'analyze',
                'compare',
                'describe',
                'discuss'
            ]),
            '{number}': str(random.randint(1, 100))
        }

        prompt = template
        for key, value in variations.items():
            prompt = prompt.replace(key, value)

        return prompt
