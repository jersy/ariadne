package com.webank.asmanalysis.asm;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 测试ClassAnalyzer的Spring注解检测功能
 */
class ClassAnalyzerSpringTest {
    private static final Logger logger = LoggerFactory.getLogger(ClassAnalyzerSpringTest.class);

    private static final String TEST_CLASS_FILE = "/Users/jersyzhang/work/callgraph-test-project/target/classes/com/example/callgraphtest/service/AsyncService.class";
    private Path testClassPath;

    @BeforeEach
    void setUp() {
        testClassPath = Paths.get(TEST_CLASS_FILE);
        assertTrue(testClassPath.toFile().exists(), "测试class文件必须存在: " + TEST_CLASS_FILE);
    }

    @Test
    void testSpringServiceAnnotationDetection() throws Exception {
        // 创建ClassAnalyzer并分析
        ClassAnalyzer analyzer = new ClassAnalyzer(testClassPath);
        analyzer.analyze();

        List<Map<String, Object>> nodes = analyzer.getNodes();
        List<Map<String, Object>> edges = analyzer.getEdges();

        logger.info("分析完成: {} nodes, {} edges", nodes.size(), edges.size());

        // 查找类节点
        Map<String, Object> classNode = null;
        for (Map<String, Object> node : nodes) {
            String nodeType = (String) node.get("nodeType");
            if ("class".equals(nodeType) || "interface".equals(nodeType)) {
                classNode = node;
                break;
            }
        }

        assertNotNull(classNode, "应该找到类节点");
        String className = (String) classNode.get("fqn");
        logger.info("测试类: {}", className);

        // 验证Spring注解检测
        assertTrue(classNode.containsKey("springBeanType"), "类节点应包含springBeanType字段");
        String springBeanType = (String) classNode.get("springBeanType");
        assertEquals("service", springBeanType, "springBeanType应该为'service'");

        // 验证其他Spring字段
        assertTrue(classNode.containsKey("springBeanName"), "类节点应包含springBeanName字段");
        assertTrue(classNode.containsKey("needsProxy"), "类节点应包含needsProxy字段");

        // needsProxy应该为true（因为@Service注解）
        Boolean needsProxy = (Boolean) classNode.get("needsProxy");
        assertTrue(needsProxy != null && needsProxy, "needsProxy应该为true");

        // 验证方法级别的@Async检测（向后兼容性检查）
        boolean foundAsyncMethod = false;
        boolean foundAsyncAttribute = false;
        for (Map<String, Object> node : nodes) {
            String nodeType = (String) node.get("nodeType");
            if ("method".equals(nodeType)) {
                Boolean isAsync = (Boolean) node.get("isAsync");
                if (isAsync != null && isAsync) {
                    foundAsyncMethod = true;
                    logger.info("找到@Async方法 (旧字段): {}", node.get("fqn"));
                }

                // 检查attributes映射中的async属性
                @SuppressWarnings("unchecked")
                Map<String, Object> attributes = (Map<String, Object>) node.get("attributes");
                if (attributes != null && Boolean.TRUE.equals(attributes.get("async"))) {
                    foundAsyncAttribute = true;
                    logger.info("找到@Async方法 (attributes): {} with attributes: {}", node.get("fqn"), attributes);
                }
            }
        }

        // AsyncService类应该包含@Async方法
        assertTrue(foundAsyncMethod, "应该至少找到一个@Async方法（旧字段检查）");
        assertTrue(foundAsyncAttribute, "应该至少找到一个@Async方法（attributes检查）");

        logger.info("Spring注解检测测试通过: {}", className);
    }

    @Test
    void testSpringAnnotationTypes() throws Exception {
        // 这个测试可以扩展来测试不同的Spring注解类型
        // 目前只测试@Service，但可以添加更多测试用例
        ClassAnalyzer analyzer = new ClassAnalyzer(testClassPath);
        analyzer.analyze();

        List<Map<String, Object>> nodes = analyzer.getNodes();

        // 查找类节点
        Map<String, Object> classNode = null;
        for (Map<String, Object> node : nodes) {
            String nodeType = (String) node.get("nodeType");
            if ("class".equals(nodeType) || "interface".equals(nodeType)) {
                classNode = node;
                break;
            }
        }

        assertNotNull(classNode, "应该找到类节点");

        // 验证所有检测到的Spring字段
        String[] expectedSpringFields = {
            "springBeanType", "springBeanName", "springScope",
            "springPrimary", "springLazy",
            "needsProxy", "isFinalClass", "hasInterfaces"
        };

        for (String field : expectedSpringFields) {
            assertTrue(classNode.containsKey(field),
                String.format("类节点应包含字段: %s", field));
            logger.info("字段 {} = {}", field, classNode.get(field));
        }
    }

    @Test
    void testMethodLevelAnnotations() throws Exception {
        ClassAnalyzer analyzer = new ClassAnalyzer(testClassPath);
        analyzer.analyze();

        List<Map<String, Object>> nodes = analyzer.getNodes();

        int methodCount = 0;
        int asyncMethodCount = 0;
        int transactionalMethodCount = 0;
        int asyncAttributeCount = 0;
        int transactionalAttributeCount = 0;

        for (Map<String, Object> node : nodes) {
            String nodeType = (String) node.get("nodeType");
            if ("method".equals(nodeType)) {
                methodCount++;

                String methodFqn = (String) node.get("fqn");
                Boolean isAsync = (Boolean) node.get("isAsync");
                Boolean isTransactional = (Boolean) node.get("isTransactional");

                if (isAsync != null && isAsync) {
                    asyncMethodCount++;
                    logger.info("@Async方法 (旧字段): {}", methodFqn);
                }

                if (isTransactional != null && isTransactional) {
                    transactionalMethodCount++;
                    logger.info("@Transactional方法 (旧字段): {}", methodFqn);
                }

                // 检查attributes映射
                @SuppressWarnings("unchecked")
                Map<String, Object> attributes = (Map<String, Object>) node.get("attributes");
                if (attributes != null) {
                    if (Boolean.TRUE.equals(attributes.get("async"))) {
                        asyncAttributeCount++;
                        logger.info("@Async方法 (attributes): {}", methodFqn);
                    }
                    if (Boolean.TRUE.equals(attributes.get("transactional"))) {
                        transactionalAttributeCount++;
                        logger.info("@Transactional方法 (attributes): {}", methodFqn);
                    }
                }
            }
        }

        logger.info("方法统计: 总共 {} 个方法, @Async: {} 个 (旧字段) / {} 个 (attributes), @Transactional: {} 个 (旧字段) / {} 个 (attributes)",
            methodCount, asyncMethodCount, asyncAttributeCount, transactionalMethodCount, transactionalAttributeCount);

        // 至少应该有一些方法
        assertTrue(methodCount > 0, "应该找到至少一个方法");
        // AsyncService应该至少有一个@Async方法（旧字段检查）
        assertTrue(asyncMethodCount > 0, "应该至少找到一个@Async方法（旧字段检查）");
        // AsyncService应该至少有一个@Async方法（attributes检查）
        assertTrue(asyncAttributeCount > 0, "应该至少找到一个@Async方法（attributes检查）");
        // 旧字段和attributes计数应该匹配
        assertEquals(asyncMethodCount, asyncAttributeCount, "@Async方法计数在旧字段和attributes中应该匹配");
        assertEquals(transactionalMethodCount, transactionalAttributeCount, "@Transactional方法计数在旧字段和attributes中应该匹配");
    }

    @Test
    void debugClassAnalyzerOutput() throws Exception {
        // 调试方法：打印ClassAnalyzer的所有输出
        ClassAnalyzer analyzer = new ClassAnalyzer(testClassPath);
        analyzer.analyze();

        List<Map<String, Object>> nodes = analyzer.getNodes();
        List<Map<String, Object>> edges = analyzer.getEdges();

        logger.info("=== DEBUG 输出 ===");
        logger.info("总共 {} 个nodes, {} 个edges", nodes.size(), edges.size());

        for (int i = 0; i < nodes.size(); i++) {
            Map<String, Object> node = nodes.get(i);
            String nodeType = (String) node.get("nodeType");
            String fqn = (String) node.get("fqn");
            logger.info("Node {}: type={}, fqn={}", i, nodeType, fqn);

            // 打印所有字段
            for (Map.Entry<String, Object> entry : node.entrySet()) {
                if (!"fqn".equals(entry.getKey()) && !"nodeType".equals(entry.getKey())) {
                    logger.info("    {} = {}", entry.getKey(), entry.getValue());
                }
            }
        }

        // 检查是否有任何节点包含Spring相关字段
        boolean hasSpringField = false;
        for (Map<String, Object> node : nodes) {
            for (String key : node.keySet()) {
                if (key.contains("spring") || key.contains("Spring") ||
                    key.contains("async") || key.contains("Async") ||
                    key.contains("proxy") || key.contains("Proxy")) {
                    logger.info("发现Spring相关字段: {} = {}", key, node.get(key));
                    hasSpringField = true;
                }
            }
        }

        if (!hasSpringField) {
            logger.warn("未发现任何Spring相关字段！");
        }

        // 打印edges的前几个
        int edgeLimit = Math.min(10, edges.size());
        logger.info("前 {} 个edges:", edgeLimit);
        for (int i = 0; i < edgeLimit; i++) {
            Map<String, Object> edge = edges.get(i);
            logger.info("Edge {}: {} -> {} ({})", i,
                edge.get("fromFqn"), edge.get("toFqn"), edge.get("edgeType"));
        }
    }
}