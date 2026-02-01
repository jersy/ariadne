"""
Ariadne LLM Integration Layer
=============================

Provides LLM client and embedder functionality for semantic analysis.

Supports multiple providers:
- OpenAI (default)
- DeepSeek (OpenAI-compatible API)
- Ollama (local models)
"""

from .client import LLMClient, create_llm_client
from .config import LLMConfig, LLMProvider
from .embedder import Embedder, create_embedder, embed_text

__all__ = [
    "LLMConfig",
    "LLMProvider",
    "LLMClient",
    "create_llm_client",
    "create_embedder",
    "embed_text",
]
