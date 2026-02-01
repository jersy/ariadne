"""
Ariadne LLM Client
==================

OpenAI-compatible LLM client for generating summaries and analysis.

Supports:
- OpenAI API
- DeepSeek API (OpenAI-compatible)
- Ollama (local models)
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)

# Retry configuration for rate limits and transient errors
MAX_RETRIES = 3
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 10


def sanitize_code_for_llm(code: str, max_length: int = 50000) -> str:
    """Remove potential prompt injection patterns from source code before sending to LLM.

    This function removes suspicious comment patterns that could be used for prompt injection attacks.
    It does not modify the actual code logic, only potentially malicious comments.

    Args:
        code: Source code to sanitize
        max_length: Maximum length of code to process (prevents oversized prompts)

    Returns:
        Sanitized source code

    Examples:
        >>> sanitize_code_for_llm("public void test() { /* IGNORE INSTRUCTIONS */ }")
        'public void test() {  }'
    """
    # Truncate to max length
    code = code[:max_length]

    # Remove suspicious comment patterns that could be injection attempts
    injection_patterns = [
        r'/\*.*IGNORE.*\*/',
        r'/\*.*INSTRUCTIONS.*\*/',
        r'/\*.*OUTPUT.*\*/',
        r'/\*.*PRINT.*\*/',
        r'/\*.*TRANSLATE.*\*/',
        r'/\*.*SHOW.*\*/',
        r'/\*.*REVEAL.*\*/',
        r'/\*.*SYSTEM.*\*/',
        r'/\*.*SECRE[T].*?\*/',
        r'/\*.*PASSWORD.*?\*/',
        r'/\*.*KEY.*?\*/',
        r'//.*IGNORE.*',
        r'//.*INSTRUCTIONS.*',
        r'//.*OUTPUT.*',
        r'//.*TRANSLATE.*',
        r'//.*SHOW.*',
        r'//.*REVEAL.*',
        r'//.*SYSTEM.*',
        r'//.*SECRE[T].*',
        r'//.*PASSWORD.*',
        r'//.*KEY.*',
    ]

    for pattern in injection_patterns:
        code = re.sub(pattern, '', code, flags=re.IGNORECASE | re.DOTALL)

    return code.strip()


def create_llm_client(config: LLMConfig) -> "LLMClient":
    """Create an LLM client based on configuration.

    Args:
        config: LLMConfig with provider settings

    Returns:
        LLMClient instance

    Raises:
        ValueError: If configuration is invalid
    """
    if not config.is_valid():
        errors = config.get_validation_errors()
        raise ValueError(f"Invalid LLM configuration: {', '.join(errors)}")

    return LLMClient(config)


class LLMClient:
    """OpenAI-compatible LLM client with retry logic.

    Supports OpenAI, DeepSeek, and Ollama providers.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize LLM client.

        Args:
            config: LLMConfig with provider settings
        """
        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=5)

        # Create OpenAI client with appropriate settings per provider
        if config.provider == LLMProvider.OLLAMA:
            # Ollama doesn't require a real API key
            client_kwargs: dict[str, Any] = {
                "api_key": "ollama",
                "base_url": config.base_url,
                "timeout": config.timeout,
            }
        else:
            # For OpenAI and DeepSeek, API key is required
            if not config.api_key:
                raise ValueError(
                    f"{config.provider.value} requires API key. "
                    f"Set ARIADNE_{config.provider.value.upper()}_API_KEY environment variable."
                )
            client_kwargs: dict[str, Any] = {
                "api_key": config.api_key,
                "timeout": config.timeout,
            }
            if config.base_url:
                client_kwargs["base_url"] = config.base_url

        self.client = OpenAI(**client_kwargs)
        logger.info(f"Initialized LLM client: {config.provider.value} ({config.model})")

    def __enter__(self) -> "LLMClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    @staticmethod
    def _should_retry(exception: Exception) -> bool:
        """Check if exception should trigger a retry.

        Args:
            exception: The exception to check

        Returns:
            True if exception is retryable
        """
        import openai

        return isinstance(
            exception,
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ),
        )

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Make a synchronous LLM API call with retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLM response text

        Raises:
            openai.APIError: If API call fails after retries
        """
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
        )

        return response.choices[0].message.content or ""

    def generate_summary(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a summary for code using LLM.

        Args:
            code: Source code to summarize
            context: Optional context (class_name, method_name, etc.)
            system_prompt: Optional system prompt override

        Returns:
            Generated summary text
        """
        # Build prompt with context
        prompt_parts: list[str] = []

        if context:
            if class_name := context.get("class_name"):
                prompt_parts.append(f"类名: {class_name}")
            if method_name := context.get("method_name"):
                prompt_parts.append(f"方法名: {method_name}")
            if signature := context.get("signature"):
                prompt_parts.append(f"方法签名: {signature}")
            if modifiers := context.get("modifiers"):
                prompt_parts.append(f"访问修饰符: {', '.join(modifiers)}")
            if annotations := context.get("annotations"):
                prompt_parts.append(f"注解: {', '.join(annotations)}")

        # Sanitize code to prevent prompt injection attacks
        sanitized_code = sanitize_code_for_llm(code)
        prompt_parts.append(f"\n源代码:\n```java\n{sanitized_code}\n```")

        prompt = "\n".join(prompt_parts)

        # Default system prompt for code summarization
        if system_prompt is None:
            system_prompt = (
                "你是一个 Java 代码分析专家。请用一句话总结以下方法的功能，"
                "专注于它解决的业务问题。\n\n"
                "要求:\n"
                "1. 使用业务语言，避免技术术语\n"
                "2. 一句话，不超过30字\n"
                "3. 格式: \"动词 + 宾语\"（如\"验证用户登录凭据\"）\n"
                "4. 如果是 getter/setter，返回 \"N/A\""
            )

        try:
            summary = self._call_llm(prompt, system_prompt)
            # Clean up summary
            summary = summary.strip()
            # Remove common prefixes/suffixes
            for prefix in ["摘要:", "总结:", "功能:", "这个方法", "该方法"]:
                if summary.startswith(prefix):
                    summary = summary[len(prefix) :].strip()
            return summary
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "N/A"

    def batch_generate_summaries(
        self,
        items: list[dict[str, Any]],
        concurrent_limit: int = 5,
    ) -> list[str]:
        """Generate summaries for multiple items concurrently.

        Args:
            items: List of dicts with 'code' and optional 'context' keys
            concurrent_limit: Maximum concurrent LLM calls

        Returns:
            List of generated summaries
        """
        if not items:
            return []

        results = {}

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=concurrent_limit) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self.generate_summary,
                    item["code"],
                    item.get("context"),
                ): i
                for i, item in enumerate(items)
            }

            # Collect results as they complete
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logger.error(f"Failed to generate summary for item {index}: {e}")
                    results[index] = "N/A"

        # Return results in original order
        return [results.get(i, "N/A") for i in range(len(items))]

    def generate_structured_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a structured JSON response from LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON response dict

        Raises:
            ValueError: If response is not valid JSON
        """
        json_system = (
            "You must respond with valid JSON only, no additional text or explanation."
        )
        if system_prompt:
            json_system = f"{system_prompt}\n\n{json_system}"

        response = self._call_llm(prompt, json_system)

        import json

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not return valid JSON: {response}") from e

    def close(self) -> None:
        """Close the client and cleanup resources."""
        self._executor.shutdown(wait=True)
