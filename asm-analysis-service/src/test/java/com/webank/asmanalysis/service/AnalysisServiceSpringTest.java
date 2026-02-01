package com.webank.asmanalysis.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 测试AnalysisService的Spring字段复制功能
 */
class AnalysisServiceSpringTest {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisServiceSpringTest.class);

    private static final String TEST_CLASS_FILE = "/Users/jersyzhang/work/callgraph-test-project/target/classes/com/example/callgraphtest/service/AsyncService.class";
    private AnalysisService analysisService;

    @BeforeEach
    void setUp() {
        analysisService = new AnalysisService();
        Path testClassPath = Paths.get(TEST_CLASS_FILE);
        assertTrue(testClassPath.toFile().exists(), "测试class文件必须存在: " + TEST_CLASS_FILE);
    }

    @Test
    void testAnalyzeWithSpringAnnotations() throws IOException {
        // 准备请求：单个class文件
        Map<String, Object> request = new HashMap<>();
        List<String> classFiles = new ArrayList<>();
        classFiles.add(TEST_CLASS_FILE);
        request.put("classFiles", classFiles);

        // 调用analyze方法
        Map<String, Object> response = analysisService.analyze(request);

        // 验证响应
        assertTrue((Boolean) response.get("success"), "分析应该成功");
        assertTrue(response.containsKey("classes"), "响应应包含classes字段");

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> classes = (List<Map<String, Object>>) response.get("classes");
        assertFalse(classes.isEmpty(), "应该至少分析到一个类");

        Map<String, Object> classData = classes.get(0);
        String className = (String) classData.get("fqn");
        logger.info("分析类: {}", className);

        // 验证Spring字段已复制到响应
        String[] expectedSpringFields = {
            "springBeanType", "springBeanName", "springScope",
            "springPrimary", "springLazy",
            "needsProxy", "proxyType"
        };

        for (String field : expectedSpringFields) {
            assertTrue(classData.containsKey(field),
                String.format("响应类数据应包含Spring字段: %s", field));
            logger.info("Spring字段 {} = {}", field, classData.get(field));
        }

        // 特别验证springBeanType
        assertEquals("service", classData.get("springBeanType"),
            "springBeanType应该为'service'");

        // 验证needsProxy
        Boolean needsProxy = (Boolean) classData.get("needsProxy");
        assertTrue(needsProxy != null && needsProxy, "needsProxy应该为true");

        // 验证方法级别的@Async检测
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> methods = (List<Map<String, Object>>) classData.get("methods");
        assertNotNull(methods, "方法列表不应为null");

        boolean foundAsyncMethod = false;
        for (Map<String, Object> method : methods) {
            Boolean isAsync = (Boolean) method.get("isAsync");
            if (isAsync != null && isAsync) {
                foundAsyncMethod = true;
                logger.info("找到@Async方法: {}", method.get("fqn"));
                break;
            }
        }

        assertTrue(foundAsyncMethod, "应该至少找到一个@Async方法");
    }

    @Test
    void testSpringFieldCopyLogging() throws IOException {
        // 这个测试验证AnalysisService是否正确记录Spring字段复制日志
        // 注意：由于日志是side effect，我们主要验证功能正确性
        Map<String, Object> request = new HashMap<>();
        List<String> classFiles = new ArrayList<>();
        classFiles.add(TEST_CLASS_FILE);
        request.put("classFiles", classFiles);

        Map<String, Object> response = analysisService.analyze(request);
        assertTrue((Boolean) response.get("success"));

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> classes = (List<Map<String, Object>>) response.get("classes");
        Map<String, Object> classData = classes.get(0);

        // 验证关键Spring字段都存在
        assertAll(
            () -> assertTrue(classData.containsKey("springBeanType"), "应有springBeanType"),
            () -> assertTrue(classData.containsKey("springBeanName"), "应有springBeanName"),
            () -> assertTrue(classData.containsKey("needsProxy"), "应有needsProxy")
        );

        logger.info("Spring字段复制验证通过，共检测到{}个字段", classData.keySet().size());
    }

    @Test
    void testMultipleClassAnalysis() throws IOException {
        // 测试分析多个class文件（虽然目前只有一个测试文件）
        Map<String, Object> request = new HashMap<>();
        List<String> classFiles = new ArrayList<>();
        classFiles.add(TEST_CLASS_FILE);
        // 可以添加更多测试文件，但目前只有一个
        request.put("classFiles", classFiles);

        Map<String, Object> response = analysisService.analyze(request);
        assertTrue((Boolean) response.get("success"));

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> classes = (List<Map<String, Object>>) response.get("classes");
        assertEquals(1, classes.size(), "应该分析到1个类");

        // 验证每个类都有Spring字段
        for (Map<String, Object> classData : classes) {
            assertTrue(classData.containsKey("springBeanType"),
                "每个类都应包含springBeanType字段");
        }
    }

    @Test
    void testClassWithNoSpringAnnotations() throws IOException {
        // 注意：这个测试需要找到一个没有Spring注解的class文件
        // 由于没有现成的测试文件，暂时跳过，但保留测试结构
        logger.info("跳过无Spring注解类测试 - 需要测试文件");
    }

    @Test
    void testDifferentSpringAnnotationTypes() throws IOException {
        // 测试不同的Spring注解类型（@Component, @Repository, @Controller等）
        // 需要相应的测试class文件，暂时记录需求
        logger.info("需要测试不同Spring注解类型的测试文件");
        logger.info("测试用例应包括：");
        logger.info("  1. @Component 注解类");
        logger.info("  2. @Repository 注解类");
        logger.info("  3. @Controller 注解类");
        logger.info("  4. @RestController 注解类");
        logger.info("  5. @Configuration 注解类");
    }
}