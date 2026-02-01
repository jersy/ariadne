"""Integration test for LLM functionality.

Tests actual LLM calls using configured API keys.
Set ARIADNE_DEEPSEEK_API_KEY and ARIADNE_OPENAI_API_KEY environment variables to run.
"""

import os
from pathlib import Path

# Load environment variables from .gitignored .env file
from dotenv import load_dotenv

load_dotenv()

# Check for required API keys
DEEPSEEK_KEY = os.environ.get("ARIADNE_DEEPSEEK_API_KEY")
OPENAI_KEY = os.environ.get("ARIADNE_OPENAI_API_KEY")

if not DEEPSEEK_KEY:
    print("WARNING: ARIADNE_DEEPSEEK_API_KEY not set. Skipping DeepSeek tests.")
if not OPENAI_KEY:
    print("WARNING: ARIADNE_OPENAI_API_KEY not set. Skipping embedding tests.")

# Configure to use DeepSeek (only if key is available)
if DEEPSEEK_KEY:
    os.environ["ARIADNE_LLM_PROVIDER"] = "deepseek"
    os.environ["ARIADNE_DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"
    os.environ["ARIADNE_DEEPSEEK_MODEL"] = "deepseek-chat"

# Configure embedder (only if key is available)
if OPENAI_KEY:
    os.environ["ARIADNE_OPENAI_BASE_URL"] = "https://api.siliconflow.cn/v1"
    os.environ["ARIADNE_OPENAI_EMBEDDING_MODEL"] = "BAAI/bge-m3"

from ariadne_llm import LLMConfig, LLMProvider, create_embedder, create_llm_client
from ariadne_llm.config import DEFAULT_DEEPSEEK_BASE_URL, DEFAULT_DEEPSEEK_MODEL


def test_llm_config():
    """Test LLM config loading."""
    if not DEEPSEEK_KEY:
        print("Skipping test_llm_config - ARIADNE_DEEPSEEK_API_KEY not set")
        return

    print("Testing LLM Config...")
    config = LLMConfig.from_env()

    print(f"  Provider: {config.provider}")
    print(f"  API Key: {'*' * 10} (configured)")
    print(f"  Base URL: {config.base_url}")
    print(f"  Model: {config.model}")
    print(f"  Embedding Model: {config.embedding_model}")
    print(f"  Valid: {config.is_valid()}")

    assert config.provider == LLMProvider.DEEPSEEK
    assert config.is_valid()
    print("  ✓ Config loaded successfully\n")


def test_llm_client():
    """Test LLM client with actual API call."""
    if not DEEPSEEK_KEY:
        print("Skipping test_llm_client - ARIADNE_DEEPSEEK_API_KEY not set")
        return

    print("Testing LLM Client...")

    config = LLMConfig.from_env()
    client = create_llm_client(config)

    # Test code summarization
    code = """public boolean login(String username, String password) {
    if (username == null || username.isEmpty()) {
        throw new IllegalArgumentException("用户名不能为空");
    }
    if (password == null || password.length() < 6) {
        throw new IllegalArgumentException("密码长度不能少于6位");
    }
    return authenticate(username, password);
}"""

    print(f"  Code: {code[:50]}...")

    try:
        summary = client.generate_summary(
            code,
            context={
                "class_name": "AuthService",
                "method_name": "login",
                "signature": "boolean login(String, String)",
                "modifiers": ["public"],
                "annotations": [],
            },
        )

        print(f"  Summary: {summary}")
        assert summary and summary != "N/A"
        print("  ✓ Summary generated successfully\n")
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        raise


def test_llm_batch_summaries():
    """Test batch summary generation."""
    if not DEEPSEEK_KEY:
        print("Skipping test_llm_batch_summaries - ARIADNE_DEEPSEEK_API_KEY not set")
        return

    print("Testing Batch Summaries...")

    config = LLMConfig.from_env()
    client = create_llm_client(config)

    items = [
        {
            "code": "public void saveUser(User user) { userRepository.save(user); }",
            "context": {"class_name": "UserService", "method_name": "saveUser"},
        },
        {
            "code": "public User findById(Long id) { return userRepository.findOne(id); }",
            "context": {"class_name": "UserService", "method_name": "findById"},
        },
        {
            "code": "public void deleteById(Long id) { userRepository.deleteById(id); }",
            "context": {"class_name": "UserService", "method_name": "deleteById"},
        },
    ]

    try:
        summaries = client.batch_generate_summaries(items, concurrent_limit=2)

        print(f"  Generated {len(summaries)} summaries:")
        for i, (item, summary) in enumerate(zip(items, summaries), 1):
            method_name = item["context"]["method_name"]
            print(f"    {i}. {method_name}: {summary}")

        assert len(summaries) == 3
        print("  ✓ Batch summaries generated successfully\n")
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        raise


def test_embedder():
    """Test embedder with actual API call."""
    if not OPENAI_KEY:
        print("Skipping test_embedder - ARIADNE_OPENAI_API_KEY not set")
        return

    print("Testing Embedder...")

    # Use OpenAI-compatible endpoint for SiliconFlow
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key=OPENAI_KEY,
        base_url="https://api.siliconflow.cn/v1",
        embedding_model="BAAI/bge-m3",
    )

    embedder = create_embedder(config)

    print(f"  Model: {config.embedding_model}")
    print(f"  Dimension: {embedder.dimension}")

    # Test single text embedding
    text = "用户登录验证"
    print(f"  Text: {text}")

    try:
        embedding = embedder.embed_text(text)

        print(f"  Embedding shape: ({len(embedding)},)")
        print(f"  First 5 values: {embedding[:5]}")

        assert len(embedding) == 1024  # BAAI/bge-m3 dimension
        print("  ✓ Embedding generated successfully\n")
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        raise


def test_vector_store():
    """Test vector store with ChromaDB."""
    print("Testing Vector Store...")

    from ariadne_core.storage.vector_store import ChromaVectorStore
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ChromaVectorStore(tmpdir)

        # Test adding summaries
        store.add_summary(
            summary_id="test_1",
            text="用户认证和登录服务",
            metadata={"fqn": "com.example.AuthService", "level": "class"},
        )

        store.add_summary(
            summary_id="test_2",
            text="订单处理和管理",
            metadata={"fqn": "com.example.OrderService", "level": "class"},
        )

        # Test getting summary
        result = store.get_summary("test_1")
        print(f"  Retrieved: {result['document']}")
        assert result is not None
        assert result["document"] == "用户认证和登录服务"

        # Test stats
        stats = store.get_stats()
        print(f"  Stats: {stats}")
        assert stats["summaries"] == 2

        print("  ✓ Vector store works successfully\n")


def test_hierarchical_summarizer():
    """Test hierarchical summarizer."""
    if not DEEPSEEK_KEY:
        print("Skipping test_hierarchical_summarizer - ARIADNE_DEEPSEEK_API_KEY not set")
        return

    print("Testing Hierarchical Summarizer...")

    from ariadne_analyzer.l1_business import HierarchicalSummarizer
    from ariadne_core.models.types import SymbolData, SymbolKind

    config = LLMConfig.from_env()
    summarizer = HierarchicalSummarizer(config)

    # Test method summarization
    method = SymbolData(
        fqn="com.example.AuthService.login",
        kind=SymbolKind.METHOD,
        name="login",
        signature="boolean login(String, String)",
        modifiers=["public"],
    )

    code = """public boolean login(String username, String password) {
    if (username == null || username.isEmpty()) {
        throw new IllegalArgumentException("用户名不能为空");
    }
    return authenticate(username, password);
}"""

    try:
        summary = summarizer.summarize_method(method, code)
        print(f"  Method: {method.name}")
        print(f"  Summary: {summary}")
        assert summary and summary != "N/A"
        print("  ✓ Hierarchical summarizer works successfully\n")
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        raise
    finally:
        summarizer.close()


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Ariadne LLM Integration Tests")
    print("=" * 60)
    print()

    try:
        test_llm_config()
        test_llm_client()
        test_llm_batch_summaries()
        test_embedder()
        test_vector_store()
        test_hierarchical_summarizer()

        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    except Exception as e:
        print("=" * 60)
        print(f"Tests failed: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
