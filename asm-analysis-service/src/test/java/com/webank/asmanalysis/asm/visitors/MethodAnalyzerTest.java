package com.webank.asmanalysis.asm.visitors;

import com.webank.asmanalysis.asm.AnalysisContext;
import com.webank.asmanalysis.asm.annotation.AnnotationProcessor;
import com.webank.asmanalysis.asm.builder.MethodMetadata;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.objectweb.asm.Opcodes;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for MethodAnalyzer.
 *
 * <p>Tests the method-level bytecode analysis including:
 * <ul>
 *   <li>Metadata creation and validation</li>
 *   <li>Annotation processing</li>
 *   <li>Method call detection</li>
 *   <li>Entry point detection</li>
 *   <li>API path mapping</li>
 * </ul>
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
@DisplayName("MethodAnalyzer Unit Tests")
public class MethodAnalyzerTest {

    private AnalysisContext context;
    private AnnotationProcessor annotationProcessor;
    private Path testClassFile;

    @BeforeEach
    public void setUp() {
        testClassFile = Paths.get("/tmp/test/TestClass.class");
        context = new AnalysisContext(testClassFile);
        context.setClassName("com.test.TestClass");
        annotationProcessor = new AnnotationProcessor(context);
    }

    @Test
    @DisplayName("Test constructor and initialization")
    public void testConstructor() {
        // Arrange
        String methodFqn = "com.test.TestClass.testMethod";
        List<String> modifiers = List.of("public");
        boolean isConstructor = false;
        List<String> paramTypes = List.of("java.lang.String");
        String returnType = "void";
        String methodName = "testMethod";
        String methodDescriptor = "(Ljava/lang/String;)V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            isConstructor,
            paramTypes,
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        assertNotNull(analyzer, "MethodAnalyzer should be created");
        MethodMetadata metadata = analyzer.getMetadata();
        assertNotNull(metadata, "Metadata should not be null");
        assertEquals(methodFqn, metadata.getFqn());
        assertEquals(methodName, metadata.getSimpleName());
        assertEquals(returnType, metadata.getReturnType());
        assertFalse(metadata.isConstructor());
        assertEquals(1, metadata.getParameterTypes().size());
    }

    @Test
    @DisplayName("Test constructor metadata for constructor")
    public void testConstructorMetadata() {
        // Arrange
        String methodFqn = "com.test.TestClass.<init>";
        List<String> modifiers = List.of("public");
        boolean isConstructor = true;
        List<String> paramTypes = List.of("java.lang.String", "int");
        String returnType = "void";
        String methodName = "<init>";
        String methodDescriptor = "(Ljava/lang/String;I)V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            isConstructor,
            paramTypes,
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertTrue(metadata.isConstructor(), "Should be marked as constructor");
        assertEquals(2, metadata.getParameterTypes().size());
        assertEquals("java.lang.String", metadata.getParameterTypes().get(0));
        assertEquals("int", metadata.getParameterTypes().get(1));
    }

    @Test
    @DisplayName("Test method with multiple parameters")
    public void testMethodWithMultipleParameters() {
        // Arrange
        String methodFqn = "com.test.TestClass.complexMethod";
        List<String> modifiers = List.of("public", "static");
        List<String> paramTypes = List.of(
            "java.lang.String",
            "java.util.List",
            "int",
            "boolean"
        );
        String returnType = "java.lang.Object";
        String methodName = "complexMethod";
        String methodDescriptor = "(Ljava/lang/String;Ljava/util/List;IZ)Ljava/lang/Object;";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            paramTypes,
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(4, metadata.getParameterTypes().size());
        assertEquals("java.lang.Object", metadata.getReturnType());
        assertEquals(2, metadata.getModifiers().size());
        assertTrue(metadata.getModifiers().contains("public"));
        assertTrue(metadata.getModifiers().contains("static"));
    }

    @Test
    @DisplayName("Test method with no parameters")
    public void testMethodWithNoParameters() {
        // Arrange
        String methodFqn = "com.test.TestClass.noParamMethod";
        List<String> modifiers = List.of("public");
        List<String> paramTypes = List.of();
        String returnType = "void";
        String methodName = "noParamMethod";
        String methodDescriptor = "()V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            paramTypes,
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertTrue(metadata.getParameterTypes().isEmpty());
        assertEquals("void", metadata.getReturnType());
    }

    @Test
    @DisplayName("Test method metadata immutability")
    public void testMetadataImmutability() {
        // Arrange
        String methodFqn = "com.test.TestClass.testMethod";
        List<String> modifiers = new java.util.ArrayList<>(List.of("public"));
        List<String> paramTypes = new java.util.ArrayList<>(List.of("java.lang.String"));

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            paramTypes,
            "void",
            "testMethod",
            "(Ljava/lang/String;)V"
        );

        // Assert - modify original lists should not affect metadata
        modifiers.add("static");
        paramTypes.add("int");

        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(1, metadata.getModifiers().size());
        assertEquals(1, metadata.getParameterTypes().size());
        assertFalse(metadata.getModifiers().contains("static"));
    }

    @Test
    @DisplayName("Test method with primitive return type")
    public void testMethodWithPrimitiveReturnType() {
        // Arrange
        String methodFqn = "com.test.TestClass.getInt";
        List<String> modifiers = List.of("public");
        String returnType = "int";
        String methodName = "getInt";
        String methodDescriptor = "()I";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals("int", metadata.getReturnType());
        assertEquals(methodName, metadata.getSimpleName());
    }

    @Test
    @DisplayName("Test method with array return type")
    public void testMethodWithArrayReturnType() {
        // Arrange
        String methodFqn = "com.test.TestClass.getArray";
        List<String> modifiers = List.of("public");
        String returnType = "java.lang.String[]";
        String methodName = "getArray";
        String methodDescriptor = "()[Ljava/lang/String;";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals("java.lang.String[]", metadata.getReturnType());
    }

    @Test
    @DisplayName("Test method with complex object return type")
    public void testMethodWithComplexReturnType() {
        // Arrange
        String methodFqn = "com.test.TestClass.getMap";
        List<String> modifiers = List.of("public");
        String returnType = "java.util.Map<java.lang.String, java.lang.Object>";
        String methodName = "getMap";
        String methodDescriptor = "()Ljava/util/Map;";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            returnType,
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals("java.util.Map<java.lang.String, java.lang.Object>", metadata.getReturnType());
    }

    @Test
    @DisplayName("Test private method metadata")
    public void testPrivateMethodMetadata() {
        // Arrange
        String methodFqn = "com.test.TestClass.privateMethod";
        List<String> modifiers = List.of("private");
        String methodName = "privateMethod";
        String methodDescriptor = "()V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            "void",
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertTrue(metadata.getModifiers().contains("private"));
        assertEquals(1, metadata.getModifiers().size());
    }

    @Test
    @DisplayName("Test protected method metadata")
    public void testProtectedMethodMetadata() {
        // Arrange
        String methodFqn = "com.test.TestClass.protectedMethod";
        List<String> modifiers = List.of("protected");
        String methodName = "protectedMethod";
        String methodDescriptor = "()V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            "void",
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertTrue(metadata.getModifiers().contains("protected"));
    }

    @Test
    @DisplayName("Test method with multiple modifiers")
    public void testMethodWithMultipleModifiers() {
        // Arrange
        String methodFqn = "com.test.TestClass.multiModifierMethod";
        List<String> modifiers = List.of("public", "static", "final", "synchronized");
        String methodName = "multiModifierMethod";
        String methodDescriptor = "()V";

        // Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            modifiers,
            false,
            List.of(),
            "void",
            methodName,
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(4, metadata.getModifiers().size());
        assertTrue(metadata.getModifiers().contains("public"));
        assertTrue(metadata.getModifiers().contains("static"));
        assertTrue(metadata.getModifiers().contains("final"));
        assertTrue(metadata.getModifiers().contains("synchronized"));
    }

    @Test
    @DisplayName("Test metadata FQN format")
    public void testMetadataFQNFormat() {
        // Arrange & Act
        String methodFqn = "com.test.service.UserService.getUserById";
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            List.of("public"),
            false,
            List.of("long"),
            "com.test.model.User",
            "getUserById",
            "(J)Lcom/test/model/User;"
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(methodFqn, metadata.getFqn());
        assertEquals("getUserById", metadata.getSimpleName());
        assertEquals("com.test.model.User", metadata.getReturnType());
        assertEquals("long", metadata.getParameterTypes().get(0));
    }

    @Test
    @DisplayName("Test metadata toString method")
    public void testMetadataToString() {
        // Arrange & Act
        String methodFqn = "com.test.TestClass.toString";
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            List.of("public"),
            false,
            List.of(),
            "java.lang.String",
            "toString",
            "()Ljava/lang/String;"
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        String toString = metadata.toString();
        assertNotNull(toString);
        assertTrue(toString.contains("MethodMetadata"));
        assertTrue(toString.contains("toString"));
        assertTrue(toString.contains("fqn="));
        assertTrue(toString.contains("simpleName="));
    }

    @Test
    @DisplayName("Test metadata attributes map")
    public void testMetadataAttributes() {
        // Arrange & Act
        String methodFqn = "com.test.TestClass.customMethod";
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            methodFqn,
            List.of("public"),
            false,
            List.of(),
            "void",
            "customMethod",
            "()V"
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        Map<String, Object> attributes = metadata.getAttributes();
        assertNotNull(attributes);
        assertTrue(attributes.isEmpty(), "New metadata should have empty attributes");
    }

    @Test
    @DisplayName("Test descriptor field in metadata")
    public void testDescriptorField() {
        // Arrange & Act
        String methodDescriptor = "(Ljava/lang/String;I)Ljava/lang/Object;";
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            "com.test.TestClass.test",
            List.of("public"),
            false,
            List.of("java.lang.String", "int"),
            "java.lang.Object",
            "test",
            methodDescriptor
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(methodDescriptor, metadata.getDescriptor());
    }

    @Test
    @DisplayName("Test metadata line number initialization")
    public void testLineNumberInitialization() {
        // Arrange & Act
        MethodAnalyzer analyzer = new MethodAnalyzer(
            context,
            annotationProcessor,
            "com.test.TestClass.test",
            List.of("public"),
            false,
            List.of(),
            "void",
            "test",
            "()V"
        );

        // Assert
        MethodMetadata metadata = analyzer.getMetadata();
        assertEquals(-1, metadata.getLineNumber(), "Initial line number should be -1");
    }
}
