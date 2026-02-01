"""
Ariadne Vector Embedder
========================

Vector embedding functionality for semantic search.

Supports:
- OpenAI embeddings API
- DeepSeek embeddings (via OpenAI-compatible endpoint)
- Ollama local embeddings
"""

import logging
from typing import Any

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from .config import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)

# Embedding dimensions by model
EMBEDDING_DIMENSIONS: dict[str, int] = {
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Ollama (common models)
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
}


def create_embedder(config: LLMConfig) -> "Embedder":
    """Create an embedder based on configuration.

    Args:
        config: LLMConfig with provider settings

    Returns:
        Embedder instance

    Raises:
        ValueError: If configuration is invalid
    """
    if not config.is_valid():
        errors = config.get_validation_errors()
        raise ValueError(f"Invalid embedder configuration: {', '.join(errors)}")

    return Embedder(config)


class Embedder:
    """Vector embedder for text embeddings.

    Supports OpenAI, DeepSeek, and Ollama providers.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize embedder.

        Args:
            config: LLMConfig with provider settings
        """
        self.config = config

        # Create OpenAI client
        client_kwargs: dict[str, Any] = {
            "api_key": config.api_key or "not-needed",
            "timeout": config.timeout,
        }

        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        self.client = OpenAI(**client_kwargs)
        self._dimension: int | None = None

        logger.info(
            f"Initialized embedder: {config.provider.value} ({config.embedding_model})"
        )

    def _get_dimension(self) -> int:
        """Get embedding dimension for current model.

        Returns:
            Embedding dimension
        """
        if self._dimension is not None:
            return self._dimension

        model = self.config.embedding_model

        # Check known models
        if model in EMBEDDING_DIMENSIONS:
            self._dimension = EMBEDDING_DIMENSIONS[model]
        else:
            # Try to detect from partial match
            model_lower = model.lower()
            for known_model, dim in EMBEDDING_DIMENSIONS.items():
                if known_model.lower() in model_lower:
                    self._dimension = dim
                    break

        # Fallback to common default
        if self._dimension is None:
            logger.warning(f"Unknown embedding model: {model}, using default dimension 768")
            self._dimension = 768

        return self._dimension

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _call_embedding_api(self, texts: list[str]) -> list[list[float]]:
        """Call embedding API with retry logic.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        response = self.client.embeddings.create(
            model=self.config.embedding_model,
            input=texts,
        )

        return [item.embedding for item in response.data]

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self._get_dimension()

        embeddings = self._call_embedding_api([text])
        return embeddings[0]

    def embed_texts(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts
        non_empty_texts = [(i, t) for i, t in enumerate(texts) if t and t.strip()]

        if not non_empty_texts:
            return [[0.0] * self._get_dimension() for _ in texts]

        # Process in batches
        results: dict[int, list[float]] = {}
        dimension = self._get_dimension()

        for i in range(0, len(non_empty_texts), batch_size):
            batch = non_empty_texts[i : i + batch_size]
            indices = [idx for idx, _ in batch]
            texts_batch = [t for _, t in batch]

            embeddings = self._call_embedding_api(texts_batch)

            for idx, embedding in zip(indices, embeddings):
                results[idx] = embedding

        # Build final results in original order
        final_results: list[list[float]] = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                final_results.append([0.0] * dimension)
            else:
                final_results.append(results[i])

        return final_results

    @property
    def dimension(self) -> int:
        """Get the embedding dimension for this embedder.

        Returns:
            Embedding dimension
        """
        return self._get_dimension()


# Convenience function for single text embedding


def embed_text(text: str, config: LLMConfig | None = None) -> list[float]:
    """Embed a single text using configuration.

    Args:
        text: Text to embed
        config: Optional LLMConfig (uses env if not provided)

    Returns:
        Embedding vector
    """
    if config is None:
        config = LLMConfig.from_env()

    embedder = create_embedder(config)
    return embedder.embed_text(text)
