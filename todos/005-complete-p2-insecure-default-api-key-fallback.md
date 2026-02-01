---
status: complete
priority: p2
issue_id: "005"
tags:
  - code-review
  - security
  - llm
dependencies: []
---

# Insecure Default API Key Fallback

## Problem Statement

The `LLMClient.__init__` uses `"not-needed"` as a default API key value when no key is provided. This fallback is misleading and could potentially be sent as an actual API key to the API.

**Location:** `ariadne_llm/client.py:72-80`

```python
client_kwargs: dict[str, Any] = {
    "api_key": config.api_key or "not-needed",  # Line 73
    "timeout": config.timeout,
}
```

## Why It Matters

1. **Misleading Fallback**: The string `"not-needed"` could mask configuration errors
2. **Potential Data Leak**: This string might accidentally be sent to the API as a credential
3. **Confusing Validation**: `config.is_valid()` checks for API key, but then it's defaulted anyway
4. **Poor Error Messages**: If API call fails, the error won't clearly indicate missing API key

## Findings

### From Security Sentinel Review:

> **Severity:** MEDIUM
> **CVE Class:** CWE-322 (Key Exchange without Entity Authentication)
>
> API key defaults to "not-needed" string. This might accidentally send "not-needed" as actual API key. Reduces confidence in API key validation.

### Current Flow:
```python
# 1. Config validation
if not config.is_valid():  # Checks if api_key exists for non-Ollama providers
    raise ValueError(...)

# 2. But then default is used anyway
"api_key": config.api_key or "not-needed"  # Why default if we validated?
```

## Proposed Solutions

### Solution 1: Explicit Provider Handling (Recommended)

**Approach:** Handle each provider explicitly without misleading defaults

**Pros:**
- Clear intent for each provider
- Fails fast on missing credentials
- No confusing fallback values

**Cons:**
- More verbose
- Requires conditional logic

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
def __init__(self, config: LLMConfig) -> None:
    self.config = config

    # Create OpenAI client with appropriate settings per provider
    if config.provider == LLMProvider.OLLAMA:
        client_kwargs = {
            "api_key": "ollama",  # Ollama requires a non-None value
            "base_url": config.base_url,
            "timeout": config.timeout,
        }
    else:
        # For OpenAI and DeepSeek, API key is required
        if not config.api_key:
            raise ValueError(
                f"{config.provider.value} requires API key. "
                f"Set {config.provider.value.upper()}_API_KEY environment variable."
            )
        client_kwargs = {
            "api_key": config.api_key,
            "timeout": config.timeout,
        }
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

    self.client = OpenAI(**client_kwargs)
    self._executor = ThreadPoolExecutor(max_workers=5)
```

## Acceptance Criteria

- [ ] Provider-specific API key handling implemented
- [ ] Ollama doesn't require API key
- [ ] OpenAI/DeepSeek raise clear error on missing API key
- [ ] Tests verify each provider's behavior
- [ ] Error messages guide users to fix configuration
- [ ] `"not-needed"` string removed from codebase

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Insecure API key fallback identified |
| 2026-02-01 | Fixed API key fallback | Implemented explicit provider handling in LLMClient.__init__ with proper error messages |

## Resources

- **Files**: `ariadne_llm/client.py`, `ariadne_llm/config.py`
- **Related**: Todo #001 (API Keys exposure) - also security related
