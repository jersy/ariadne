"""Unit tests for ariadne_llm client module."""

from unittest.mock import MagicMock, patch

import pytest

from ariadne_llm.config import LLMConfig, LLMProvider


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_from_env_openai(self, monkeypatch):
        """Test loading OpenAI config from environment."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("ARIADNE_OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("ARIADNE_OPENAI_MODEL", "gpt-4")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "sk-test-key"
        assert config.model == "gpt-4"

    def test_from_env_deepseek(self, monkeypatch):
        """Test loading DeepSeek config from environment."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("ARIADNE_DEEPSEEK_API_KEY", "sk-deepseek-key")
        monkeypatch.setenv("ARIADNE_DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.DEEPSEEK
        assert config.api_key == "sk-deepseek-key"
        assert config.base_url == "https://api.deepseek.com"

    def test_from_env_ollama(self, monkeypatch):
        """Test loading Ollama config from environment."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("ARIADNE_OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("ARIADNE_OLLAMA_MODEL", "deepseek-r1:7b")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.OLLAMA
        assert config.base_url == "http://localhost:11434"
        assert config.model == "deepseek-r1:7b"

    def test_validation_openai_missing_key(self, monkeypatch):
        """Test validation fails without API key for OpenAI."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "openai")
        monkeypatch.delenv("ARIADNE_OPENAI_API_KEY", raising=False)

        config = LLMConfig.from_env()

        assert not config.is_valid()
        errors = config.get_validation_errors()
        # Check that error message contains the key name
        assert any("ARIADNE_OPENAI_API_KEY" in e for e in errors)

    def test_validation_ollama_no_api_key_needed(self, monkeypatch):
        """Test Ollama doesn't require API key."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("ARIADNE_OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("ARIADNE_OLLAMA_MODEL", "deepseek-r1:7b")

        config = LLMConfig.from_env()

        assert config.is_valid()


class TestLLMClient:
    """Tests for LLMClient."""

    def test_create_client_requires_valid_config(self, monkeypatch):
        """Test that client creation fails with invalid config."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "openai")
        monkeypatch.delenv("ARIADNE_OPENAI_API_KEY", raising=False)

        config = LLMConfig.from_env()

        with pytest.raises(ValueError, match="Invalid LLM configuration"):
            from ariadne_llm.client import create_llm_client

            create_llm_client(config)

    @patch("ariadne_llm.client.OpenAI")
    def test_generate_summary(self, mock_openai):
        """Test generating a summary."""
        from ariadne_llm.client import create_llm_client

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "验证用户登录凭据"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        client = create_llm_client(config)

        summary = client.generate_summary(
            "public boolean login(String user) { return true; }",
            context={"class_name": "AuthService", "method_name": "login"},
        )

        assert summary == "验证用户登录凭据"
        mock_client.chat.completions.create.assert_called_once()

    @patch("ariadne_llm.client.OpenAI")
    def test_generate_structured_response(self, mock_openai):
        """Test generating structured JSON response."""
        import json

        from ariadne_llm.client import create_llm_client

        # Mock OpenAI response
        mock_response = {
            "business_meaning": "用户认证服务",
            "synonyms": ["登录", "认证"],
        }

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps(mock_response)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai.return_value = mock_client

        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        client = create_llm_client(config)

        result = client.generate_structured_response("Extract business meaning")

        assert result["business_meaning"] == "用户认证服务"
        assert result["synonyms"] == ["登录", "认证"]

    @patch("ariadne_llm.client.OpenAI")
    def test_retry_on_rate_limit(self, mock_openai):
        """Test that client retries on rate limit errors."""
        from ariadne_llm.client import create_llm_client

        # First call fails with exception, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary text"

        # Create a mock exception that simulates rate limit
        mock_exception = Exception("Rate limit exceeded")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            mock_exception,
            mock_response,
        ]
        mock_openai.return_value = mock_client

        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        client = create_llm_client(config)

        summary = client.generate_summary("code", context={})

        assert summary == "Summary text"
        assert mock_client.chat.completions.create.call_count == 2


class TestEmbedder:
    """Tests for Embedder."""

    def test_create_embedder_requires_valid_config(self, monkeypatch):
        """Test that embedder creation fails with invalid config."""
        monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "openai")
        monkeypatch.delenv("ARIADNE_OPENAI_API_KEY", raising=False)

        config = LLMConfig.from_env()

        with pytest.raises(ValueError, match="Invalid embedder configuration"):
            from ariadne_llm.embedder import create_embedder

            create_embedder(config)

    @patch("ariadne_llm.embedder.OpenAI")
    def test_embed_text(self, mock_openai):
        """Test embedding a single text."""
        import numpy as np

        from ariadne_llm.embedder import create_embedder

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        embedder = create_embedder(config)

        embedding = embedder.embed_text("test text")

        assert len(embedding) == 1536
        assert embedding[0] == 0.1

    @patch("ariadne_llm.embedder.OpenAI")
    def test_embedding_dimension_known_model(self, mock_openai):
        """Test embedding dimension for known model."""
        from ariadne_llm.embedder import create_embedder

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            embedding_model="text-embedding-3-small",
        )
        embedder = create_embedder(config)

        assert embedder.dimension == 1536

    @patch("ariadne_llm.embedder.OpenAI")
    def test_embedding_dimension_unknown_model(self, mock_openai):
        """Test embedding dimension falls back for unknown model."""
        from ariadne_llm.embedder import create_embedder

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            embedding_model="unknown-model",
        )
        embedder = create_embedder(config)

        # Should fall back to 768 default
        assert embedder.dimension == 768
