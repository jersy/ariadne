"""Demo script showing Ariadne L1 Business Layer capabilities.

This demonstrates:
- LLM-based code summarization
- Hierarchical summarization (Method → Class → Package)
- Semantic search using vector embeddings
- Vector storage with ChromaDB

Required Environment Variables:
- ARIADNE_DEEPSEEK_API_KEY: For LLM summarization
- ARIADNE_OPENAI_API_KEY: For embeddings (SiliconFlow endpoint)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .gitignored .env file
load_dotenv()

# Check for required API keys
DEEPSEEK_KEY = os.environ.get("ARIADNE_DEEPSEEK_API_KEY")
OPENAI_KEY = os.environ.get("ARIADNE_OPENAI_API_KEY")

if not DEEPSEEK_KEY:
    print("ERROR: ARIADNE_DEEPSEEK_API_KEY not set")
    print("Please set the ARIADNE_DEEPSEEK_API_KEY environment variable")
    sys.exit(1)

if not OPENAI_KEY:
    print("ERROR: ARIADNE_OPENAI_API_KEY not set")
    print("Please set the ARIADNE_OPENAI_API_KEY environment variable")
    sys.exit(1)

# Configure to use DeepSeek
os.environ["ARIADNE_LLM_PROVIDER"] = "deepseek"
os.environ["ARIADNE_DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"
os.environ["ARIADNE_DEEPSEEK_MODEL"] = "deepseek-chat"

# Configure embedder to use SiliconFlow
os.environ["ARIADNE_OPENAI_BASE_URL"] = "https://api.siliconflow.cn/v1"
os.environ["ARIADNE_OPENAI_EMBEDDING_MODEL"] = "BAAI/bge-m3"

from ariadne_llm import LLMConfig, LLMProvider, create_embedder, create_llm_client
from ariadne_analyzer.l1_business import HierarchicalSummarizer
from ariadne_core.models.types import SymbolData, SymbolKind, SummaryData, SummaryLevel
from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_core.storage.vector_store import ChromaVectorStore
import tempfile


def demo_llm_summarization():
    """Demo: LLM-based code summarization."""
    print("\n" + "=" * 60)
    print("Demo 1: LLM Code Summarization")
    print("=" * 60)

    config = LLMConfig.from_env()
    client = create_llm_client(config)

    # Example Java code
    codes = [
        {
            "name": "UserService.login",
            "code": """
public boolean login(String username, String password) {
    if (username == null || username.isEmpty()) {
        throw new IllegalArgumentException("用户名不能为空");
    }
    User user = userRepository.findByUsername(username);
    if (user == null || !user.checkPassword(password)) {
        throw new AuthenticationException("认证失败");
    }
    user.setLastLoginTime(LocalDateTime.now());
    userRepository.save(user);
    return true;
}
""",
        },
        {
            "name": "OrderService.createOrder",
            "code": """
public Order createOrder(OrderRequest request) {
    Order order = new Order();
    order.setUserId(request.getUserId());
    order.setItems(request.getItems());

    // 验证库存
    for (OrderItem item : order.getItems()) {
        Product product = productService.getById(item.getProductId());
        if (product.getStock() < item.getQuantity()) {
            throw new InsufficientStockException("库存不足: " + product.getName());
        }
    }

    // 计算订单金额
    BigDecimal total = calculateTotal(order);
    order.setTotalAmount(total);

    return orderRepository.save(order);
}
""",
        },
    ]

    for item in codes:
        print(f"\n代码: {item['name']}")
        print("-" * 40)
        summary = client.generate_summary(
            item["code"],
            context={"class_name": item["name"].split(".")[0], "method_name": item["name"].split(".")[-1]},
        )
        print(f"摘要: {summary}")


def demo_hierarchical_summarization():
    """Demo: Hierarchical summarization (Method → Class → Package)."""
    print("\n" + "=" * 60)
    print("Demo 2: Hierarchical Summarization")
    print("=" * 60)

    config = LLMConfig.from_env()
    summarizer = HierarchicalSummarizer(config)

    # Simulate a class with multiple methods
    class_name = "UserService"
    methods = [
        ("login", "boolean login(String, String)", "验证用户登录凭证"),
        ("register", "void register(UserRegistrationDto)", "注册新用户"),
        ("updateProfile", "void updateProfile(Long, UserProfile)", "更新用户资料"),
        ("changePassword", "void changePassword(Long, String, String)", "修改用户密码"),
        ("resetPassword", "void resetPassword(String)", "重置用户密码"),
    ]

    print(f"\n类: {class_name}")
    print("-" * 40)

    # Generate class summary from method summaries
    method_summaries = [(name, summary) for name, _, summary in methods]
    class_summary = summarizer.summarize_class(
        SymbolData(
            fqn="com.example.UserService",
            kind=SymbolKind.CLASS,
            name=class_name,
            annotations=["Service"],
        ),
        method_summaries,
        "Service",
    )

    print(f"方法列表:")
    for name, _, summary in methods:
        print(f"  - {name}: {summary}")
    print(f"\n类摘要: {class_summary}")


def demo_semantic_search():
    """Demo: Semantic search using vector embeddings."""
    print("\n" + "=" * 60)
    print("Demo 3: Semantic Search")
    print("=" * 60)

    # Configure embedder for SiliconFlow
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key=OPENAI_KEY,
        base_url="https://api.siliconflow.cn/v1",
        embedding_model="BAAI/bge-m3",
    )

    embedder = create_embedder(config)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ChromaVectorStore(tmpdir)

        # Add sample summaries to vector store
        summaries = [
            ("user_service", "用户服务：处理用户注册、登录、资料管理等功能", "class"),
            ("order_service", "订单服务：处理订单创建、支付、发货等流程", "class"),
            ("auth_service", "认证服务：处理用户认证和授权", "class"),
            ("inventory_service", "库存服务：管理商品库存和出入库", "class"),
            ("payment_service", "支付服务：处理订单支付和退款", "class"),
        ]

        print("\n存储的业务摘要:")
        for fqn, text, level in summaries:
            # Generate embedding
            embedding = embedder.embed_text(text)
            # Store in vector DB
            store.add_summary(fqn, text, embedding, {"fqn": fqn, "level": level})
            print(f"  - {fqn}: {text}")

        # Test semantic search
        queries = [
            "用户登录",
            "订单处理",
            "商品库存",
            "验证码",
        ]

        print("\n语义搜索测试:")
        for query in queries:
            query_embedding = embedder.embed_text(query)
            results = store.search_summaries(query_embedding, n_results=3)

            print(f"\n查询: '{query}'")
            print("  相关结果:")
            if results["ids"] and results["ids"][0]:
                for i, (fqn, doc, dist) in enumerate(
                    zip(results["ids"][0], results["documents"][0], results["distances"][0]), 1
                ):
                    similarity = 1 - dist
                    print(f"    {i}. {fqn}: {doc} (相似度: {similarity:.2f})")


def demo_persistence():
    """Demo: Integration with SQLite for persistent storage."""
    print("\n" + "=" * 60)
    print("Demo 4: SQLite + Vector Store Integration")
    print("=" * 60)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / "ariadne.db"
        vector_path = tmpdir_path / "vectors"

        # Initialize stores
        sqlite_store = SQLiteStore(str(db_path), init=True)
        vector_store = ChromaVectorStore(vector_path)

        # Configure embedder
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key=OPENAI_KEY,
            base_url="https://api.siliconflow.cn/v1",
            embedding_model="BAAI/bge-m3",
        )
        embedder = create_embedder(config)

        try:
            # Create summaries
            summaries_data = [
                SummaryData(
                    target_fqn="com.example.UserService",
                    level=SummaryLevel.CLASS,
                    summary="用户服务：处理用户注册、登录、资料管理",
                ),
                SummaryData(
                    target_fqn="com.example.OrderService",
                    level=SummaryLevel.CLASS,
                    summary="订单服务：处理订单创建、支付、发货",
                ),
            ]

            # Store in SQLite
            for summary in summaries_data:
                sqlite_store.create_summary(summary)

            # Store embeddings in vector store
            for summary in summaries_data:
                embedding = embedder.embed_text(summary.summary)
                vector_store.add_summary(
                    summary_id=summary.target_fqn,
                    text=summary.summary,
                    embedding=embedding,
                    metadata={"level": summary.level.value},
                )

            print("\n已存储摘要:")
            for summary in summaries_data:
                print(f"  - {summary.target_fqn}: {summary.summary}")

            # Verify SQLite storage
            print("\nSQLite 查询结果:")
            retrieved = sqlite_store.get_summary("com.example.UserService")
            print(f"  FQN: {retrieved['target_fqn']}")
            print(f"  Level: {retrieved['level']}")
            print(f"  Summary: {retrieved['summary']}")

            # Verify vector storage
            print("\n向量存储统计:")
            stats = vector_store.get_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")

        finally:
            sqlite_store.close()


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("Ariadne L1 Business Layer - Feature Demonstration")
    print("=" * 60)
    print("\nUsing DeepSeek for LLM and SiliconFlow for embeddings")

    try:
        demo_llm_summarization()
        demo_hierarchical_summarization()
        demo_semantic_search()
        demo_persistence()

        print("\n" + "=" * 60)
        print("All demos completed successfully! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
