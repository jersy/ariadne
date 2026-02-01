"""
LLM Cost Tracker
================

Tracks token usage and API costs for LLM operations.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMCostTracker:
    """Track LLM API usage and costs.

    Provides cost estimation based on token usage for different models.
    """

    # Cost per 1K tokens (input + output)
    MODEL_COSTS: dict[str, float] = field(default_factory=lambda: {
        # OpenAI pricing (as of 2025)
        "gpt-4o": 0.005,
        "gpt-4o-mini": 0.00015,
        "gpt-4-turbo": 0.01,
        "gpt-3.5-turbo": 0.001,
        # DeepSeek pricing
        "deepseek-chat": 0.0001,
        "deepseek-coder": 0.0001,
        # Zhipu/GLM pricing
        "glm-4-flash": 0.0001,
        "glm-4-plus": 0.0005,
        "glm-4-air": 0.0001,
        # Ollama (free)
        "ollama": 0.0,
    })

    usage: dict[str, Any] = field(default_factory=lambda: {
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "requests_count": 0,
        "cached_count": 0,
        "model_costs": {},
    })

    def record_request(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
    ) -> None:
        """Record an LLM API request.

        Args:
            model: Model name used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached: Whether this was a cached response
        """
        total_tokens = input_tokens + output_tokens

        # Get cost per 1K tokens for this model
        cost_per_1k = self.MODEL_COSTS.get(model, 0.001)
        cost = total_tokens / 1000 * cost_per_1k

        # Update totals
        self.usage["total_tokens"] += total_tokens
        self.usage["total_cost_usd"] += cost
        self.usage["requests_count"] += 1
        if cached:
            self.usage["cached_count"] += 1

        # Track per-model costs
        if model not in self.usage["model_costs"]:
            self.usage["model_costs"][model] = {"tokens": 0, "cost": 0.0, "requests": 0}

        self.usage["model_costs"][model]["tokens"] += total_tokens
        self.usage["model_costs"][model]["cost"] += cost
        self.usage["model_costs"][model]["requests"] += 1

    def get_report(self) -> str:
        """Generate a cost report string.

        Returns:
            Formatted cost report
        """
        lines = [
            "LLM Usage Report:",
            f"  Total Requests: {self.usage['requests_count']:,}",
            f"  Cached: {self.usage['cached_count']:,}",
            f"  Total Tokens: {self.usage['total_tokens']:,}",
            f"  Total Cost: ${self.usage['total_cost_usd']:.4f}",
        ]

        if self.usage["model_costs"]:
            lines.append("\n  By Model:")
            for model, stats in self.usage["model_costs"].items():
                lines.append(
                    f"    {model}: {stats['requests']:,} requests, "
                    f"{stats['tokens']:,} tokens, ${stats['cost']:.4f}"
                )

        return "\n".join(lines)

    def get_summary(self) -> dict[str, Any]:
        """Get usage summary as a dict.

        Returns:
            Dict with usage statistics
        """
        return self.usage.copy()

    def reset(self) -> None:
        """Reset all tracking."""
        self.usage = {
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "requests_count": 0,
            "cached_count": 0,
            "model_costs": {},
        }
