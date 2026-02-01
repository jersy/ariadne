---
category: security
module: llm-integration
symptoms:
  - API keys exposed in source code
  - Tests fail without credentials
  - No configuration template
tags:
  - security
  - llm
  - tests
  - credentials
---

# Hardcoded API Keys in Test Files

## Problem

LLM API keys were hardcoded in test files (`tests/test_llm_integration.py`, `tests/demo_l1_features.py`), exposing credentials in source control and causing tests to fail for other developers.

## Detection

Tests contained literal API key strings:
```python
# tests/test_llm_integration.py
LLM_CLIENT = LLMClient(
    provider=LLMProvider.DEEPSEEK,
    api_key="sk-1234567890abcdef"  # EXPOSED!
)
```

## Solution

### 1. Remove Hardcoded Keys

Replace hardcoded keys with environment variable lookups:

```python
# tests/test_llm_integration.py
import os

api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    pytest.skip("DEEPSEEK_API_KEY not set")

LLM_CLIENT = LLMClient(
    provider=LLMProvider.DEEPSEEK,
    api_key=api_key
)
```

### 2. Add Configuration Template

Create `.env.example` with placeholders:

```bash
# .env.example
# LLM Provider Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Secure Key Display in Tests

When displaying keys in test output, mask them:

```python
# Instead of: print(f"Using key: {api_key}")
print(f"Using key: {'*' * 10}")
```

## Prevention

1. Add `.env` to `.gitignore`
2. Add pre-commit hook to detect API keys:
   ```bash
   # .git/hooks/pre-commit
   git diff --cached | grep -E "sk-[a-zA-Z0-9]{32}" && exit 1
   ```
3. Use secret scanning tools (truffleHog, gitleaks)

## Files Changed

- `tests/test_llm_integration.py` - Remove hardcoded keys, add env var checks
- `tests/demo_l1_features.py` - Add env var validation with sys.exit(1)
- `.env.example` - Create configuration template

## Related

- Todo #001: Hardcoded API keys security vulnerability
- Security: Credential exposure in version control
- Testing: Environment-specific configuration
