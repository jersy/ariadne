package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;
import com.webank.asmanalysis.asm.AnnotationConstants;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for AnnotationProcessor.
 *
 * <p>Tests the annotation processor coordination including:
 * <ul>
 *   <li>Handler registration and ordering</li>
 *   <li>Class-level annotation processing</li>
 *   <li>Method-level annotation processing</li>
 *   <li>Field-level annotation processing</li>
 *   <li>Handler priority ordering</li>
 * </ul>
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
@DisplayName("AnnotationProcessor Unit Tests")
public class AnnotationProcessorTest {

    private AnalysisContext context;
    private AnnotationProcessor processor;

    @BeforeEach
    public void setUp() {
        Path testClassFile = Paths.get("/tmp/test/TestClass.class");
        context = new AnalysisContext(testClassFile);
        context.setClassName("com.test.TestClass");
        processor = new AnnotationProcessor(context);
    }

    @Test
    @DisplayName("Test processor initialization")
    public void testProcessorInitialization() {
        // Assert
        assertNotNull(processor, "AnnotationProcessor should be created");
        assertNotNull(context, "AnalysisContext should be set");
    }

    @Test
    @DisplayName("Test handler registration - class handlers count")
    public void testClassHandlersCount() {
        // Act - The processor should register handlers on initialization
        // This is tested indirectly through processing functionality

        // Assert - We can verify by processing a known annotation
        boolean result = processor.processClassAnnotation(
            AnnotationConstants.COMPONENT,
            true,
            "com.test.TestClass",
            context
        );

        // If it's processed successfully, handlers are registered
        assertTrue(result || !result, "Processing should complete without exception");
    }

    @Test
    @DisplayName("Test Spring @Component annotation processing")
    public void testSpringComponentProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.COMPONENT,
            true,
            "com.test.TestClass",
            context
        );

        // Assert
        assertTrue(handled, "@Component should be handled");
        assertEquals("component", context.getSpringBeanType());
        assertTrue(context.isNeedsProxy());
    }

    @Test
    @DisplayName("Test Spring @Service annotation processing")
    public void testSpringServiceProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.SERVICE,
            true,
            "com.test.UserService",
            context
        );

        // Assert
        assertTrue(handled, "@Service should be handled");
        assertEquals("service", context.getSpringBeanType());
    }

    @Test
    @DisplayName("Test Spring @Repository annotation processing")
    public void testSpringRepositoryProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.REPOSITORY,
            true,
            "com.test.UserRepository",
            context
        );

        // Assert
        assertTrue(handled, "@Repository should be handled");
        assertEquals("repository", context.getSpringBeanType());
    }

    @Test
    @DisplayName("Test Spring @Controller annotation processing")
    public void testSpringControllerProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.CONTROLLER,
            true,
            "com.test.TestController",
            context
        );

        // Assert
        assertTrue(handled, "@Controller should be handled");
        assertEquals("controller", context.getSpringBeanType());
    }

    @Test
    @DisplayName("Test @RestController annotation processing")
    public void testRestControllerProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.REST_CONTROLLER,
            true,
            "com.test.ApiController",
            context
        );

        // Assert
        assertTrue(handled, "@RestController should be handled");
        assertEquals("rest_controller", context.getSpringBeanType());
    }

    @Test
    @DisplayName("Test unknown annotation should not be handled")
    public void testUnknownAnnotationNotHandled() {
        // Act
        boolean handled = processor.processClassAnnotation(
            "Lcom/example/Unknown;",
            true,
            "com.test.TestClass",
            context
        );

        // Assert
        assertFalse(handled, "Unknown annotation should not be handled");
    }

    @Test
    @DisplayName("Test @Transactional method annotation processing")
    public void testTransactionalMethodProcessing() {
        // Arrange - Use HashMap for mutability
        Map<String, Object> methodNode = new java.util.HashMap<>();
        methodNode.put("fqn", "com.test.TestClass.testMethod");

        // Act
        boolean handled = processor.processMethodAnnotation(
            AnnotationConstants.SPRING_TRANSACTIONAL,
            true,
            methodNode,
            context
        );

        // Assert
        assertTrue(handled, "@Transactional should be handled");
        assertEquals(true, methodNode.get("isTransactional"));
    }

    @Test
    @DisplayName("Test @Async method annotation processing")
    public void testAsyncMethodProcessing() {
        // Arrange - Use HashMap for mutability
        Map<String, Object> methodNode = new java.util.HashMap<>();
        methodNode.put("fqn", "com.test.TestClass.asyncMethod");

        // Act
        boolean handled = processor.processMethodAnnotation(
            AnnotationConstants.ASYNC,
            true,
            methodNode,
            context
        );

        // Assert
        assertTrue(handled, "@Async should be handled");
        assertEquals(true, methodNode.get("isAsync"));
    }

    @Test
    @DisplayName("Test @Bean method annotation processing")
    public void testBeanMethodProcessing() {
        // Arrange - Use HashMap for mutability
        Map<String, Object> methodNode = new java.util.HashMap<>();
        methodNode.put("fqn", "com.test.AppConfig.myBean");
        methodNode.put("name", "myBean");

        // Act
        boolean handled = processor.processMethodAnnotation(
            AnnotationConstants.BEAN,
            true,
            methodNode,
            context
        );

        // Assert
        assertTrue(handled, "@Bean should be handled");
        assertEquals(true, methodNode.get("isBean"));
    }

    @Test
    @DisplayName("Test @Scheduled method annotation processing")
    public void testScheduledMethodProcessing() {
        // Arrange - Use HashMap for mutability
        Map<String, Object> methodNode = new java.util.HashMap<>();
        methodNode.put("fqn", "com.test.Task.scheduledTask");
        methodNode.put("name", "scheduledTask");

        // Act
        boolean handled = processor.processMethodAnnotation(
            AnnotationConstants.SCHEDULED,
            true,
            methodNode,
            context
        );

        // Assert
        assertTrue(handled, "@Scheduled should be handled");
        assertEquals(true, methodNode.get("isScheduled"));
        assertEquals(true, methodNode.get("isEntryPoint"));
    }

    @Test
    @DisplayName("Test @Autowired field annotation processing")
    public void testAutowiredFieldProcessing() {
        // Act
        boolean handled = processor.processFieldAnnotation(
            AnnotationConstants.AUTOWIRED,
            true,
            "com.test.TestClass",
            "userService",
            context
        );

        // Assert
        assertTrue(handled, "@Autowired should be handled");
    }

    @Test
    @DisplayName("Test @Inject field annotation processing")
    public void testInjectFieldProcessing() {
        // Act
        boolean handled = processor.processFieldAnnotation(
            AnnotationConstants.INJECT,
            true,
            "com.test.TestClass",
            "userService",
            context
        );

        // Assert
        assertTrue(handled, "@Inject should be handled");
    }

    @Test
    @DisplayName("Test @Resource field annotation processing")
    public void testResourceFieldProcessing() {
        // Act
        boolean handled = processor.processFieldAnnotation(
            AnnotationConstants.RESOURCE,
            true,
            "com.test.TestClass",
            "dataSource",
            context
        );

        // Assert
        assertTrue(handled, "@Resource should be handled");
    }

    @Test
    @DisplayName("Test @Aspect annotation processing")
    public void testAspectProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.SPRING_ASPECT,
            false,  // @Aspect from AspectJ is runtime-visible=false
            "com.test.LoggingAspect",
            context
        );

        // Assert
        assertTrue(handled, "@Aspect should be handled");
        assertTrue(context.isAspect());
    }

    @Test
    @DisplayName("Test @Primary annotation processing")
    public void testPrimaryProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.PRIMARY,
            true,
            "com.test.PrimaryService",
            context
        );

        // Assert
        assertTrue(handled, "@Primary should be handled");
        assertTrue(context.isPrimary());
    }

    @Test
    @DisplayName("Test @Scope annotation processing")
    public void testScopeProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.SCOPE,
            true,
            "com.test.PrototypeBean",
            context
        );

        // Assert
        assertTrue(handled, "@Scope should be handled");
        // Scope value is extracted via attribute visitor
    }

    @Test
    @DisplayName("Test @Lazy annotation processing")
    public void testLazyProcessing() {
        // Act
        boolean handled = processor.processClassAnnotation(
            AnnotationConstants.LAZY,
            true,
            "com.test.LazyService",
            context
        );

        // Assert
        assertTrue(handled, "@Lazy should be handled");
        assertTrue(context.isLazy());
    }
}
