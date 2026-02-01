"""
Ariadne LLM Configuration
=========================

Configuration for LLM providers and embedding models.

Environment Variables:
    ARIADNE_LLM_PROVIDER: openai|deepseek|ollama (default: openai)
    ARIADNE_OPENAI_API_KEY: OpenAI API key
    ARIADNE_OPENAI_MODEL: Model for LLM (default: gpt-4o-mini)
    ARIADNE_OPENAI_EMBEDDING_MODEL: Model for embeddings (default: text-embedding-3-small)
    ARIADNE_DEEPSEEK_API_KEY: DeepSeek API key
    ARIADNE_DEEPSEEK_BASE_URL: DeepSeek API URL (default: https://api.deepseek.com)
    ARIADNE_DEEPSEEK_MODEL: Model for LLM (default: deepseek-chat)
    ARIADNE_OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
    ARIADNE_OLLAMA_MODEL: Model for LLM (default: deepseek-r1:7b)
    ARIADNE_OLLAMA_EMBEDDING_MODEL: Model for embeddings
"""

import os
from dataclasses import dataclass
from enum import Enum

# Default configuration values
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for LLM client and embedder.

    Attributes:
        provider: LLM provider (openai, deepseek, ollama)
        api_key: API key for the provider
        base_url: Base URL for API (for DeepSeek/Ollama)
        model: Model name for LLM
        embedding_model: Model name for embeddings
        max_tokens: Maximum tokens for LLM response
        temperature: Temperature for LLM sampling
        timeout: Request timeout in seconds
        max_workers: Maximum concurrent LLM requests (for batch operations)
        request_timeout: Per-request timeout in seconds (for batch operations)
    """

    provider: LLMProvider = LLMProvider.OPENAI
    api_key: str = ""
    base_url: str = ""
    model: str = DEFAULT_OPENAI_MODEL
    embedding_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    timeout: int = 120
    max_workers: int = 10
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create configuration from environment variables.

        Returns:
            LLMConfig instance with values from environment
        """
        provider_str = os.environ.get("ARIADNE_LLM_PROVIDER", "openai").lower()
        provider = LLMProvider(provider_str)

        config = cls(provider=provider)

        if provider == LLMProvider.OPENAI:
            config.api_key = os.environ.get("ARIADNE_OPENAI_API_KEY", "")
            config.model = os.environ.get("ARIADNE_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
            config.embedding_model = os.environ.get(
                "ARIADNE_OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_EMBEDDING_MODEL
            )
            config.base_url = ""

        elif provider == LLMProvider.DEEPSEEK:
            config.api_key = os.environ.get("ARIADNE_DEEPSEEK_API_KEY", "")
            config.base_url = os.environ.get(
                "ARIADNE_DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL
            )
            config.model = os.environ.get("ARIADNE_DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
            # DeepSeek uses same model for embeddings (via OpenAI compatible endpoint)
            config.embedding_model = config.model

        elif provider == LLMProvider.OLLAMA:
            config.base_url = os.environ.get(
                "ARIADNE_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL
            )
            config.model = os.environ.get("ARIADNE_OLLAMA_MODEL", "deepseek-r1:7b")
            config.embedding_model = os.environ.get(
                "ARIADNE_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
            )
            config.api_key = "ollama"  # Ollama doesn't need API key

        return config

    def is_valid(self) -> bool:
        """Check if configuration has minimum required values.

        Returns:
            True if configuration is valid for operation
        """
        if self.provider == LLMProvider.OLLAMA:
            # Ollama doesn't require API key
            return bool(self.base_url and self.model)
        return bool(self.api_key)

    def get_validation_errors(self) -> list[str]:
        """Get list of validation errors.

        Returns:
            List of validation error messages
        """
        errors = []

        if self.provider == LLMProvider.OPENAI:
            if not self.api_key:
                errors.append("OpenAI provider requires ARIADNE_OPENAI_API_KEY")
        elif self.provider == LLMProvider.DEEPSEEK:
            if not self.api_key:
                errors.append("DeepSeek provider requires ARIADNE_DEEPSEEK_API_KEY")
        elif self.provider == LLMProvider.OLLAMA:
            if not self.base_url:
                errors.append("Ollama provider requires ARIADNE_OLLAMA_BASE_URL")
            if not self.model:
                errors.append("Ollama provider requires ARIADNE_OLLAMA_MODEL")

        return errors
