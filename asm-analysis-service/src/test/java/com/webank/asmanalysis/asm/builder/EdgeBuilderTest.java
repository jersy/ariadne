package com.webank.asmanalysis.asm.builder;

import com.webank.asmanalysis.asm.AnalysisContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for EdgeBuilder.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
@DisplayName("EdgeBuilder Unit Tests")
public class EdgeBuilderTest {

    private AnalysisContext context;
    private EdgeBuilder edgeBuilder;

    @BeforeEach
    public void setUp() {
        Path testClassFile = Paths.get("/tmp/test/TestClass.class");
        context = new AnalysisContext(testClassFile);
        edgeBuilder = new EdgeBuilder(context);
    }

    @Test
    @DisplayName("Test createMemberEdge")
    public void testCreateMemberEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createMemberEdge(
            "com.test.TestClass.method",
            "com.test.TestClass",
            "method"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("member_of", edge.get("edgeType"));
        assertEquals("com.test.TestClass.method", edge.get("fromFqn"));
        assertEquals("com.test.TestClass", edge.get("toFqn"));
        assertEquals("method", edge.get("kind"));

        // Verify edge was added to context
        List<Map<String, Object>> edges = context.getEdges();
        assertEquals(1, edges.size());
        assertEquals(edge, edges.get(0));
    }

    @Test
    @DisplayName("Test createReturnEdge")
    public void testCreateReturnEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createReturnEdge(
            "java.lang.String",
            "com.test.TestClass.toString"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("member_of", edge.get("edgeType"));
        assertEquals("return", edge.get("kind"));
        assertEquals("java.lang.String", edge.get("fromFqn"));
        assertEquals("com.test.TestClass.toString", edge.get("toFqn"));
    }

    @Test
    @DisplayName("Test createParameterEdge")
    public void testCreateParameterEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createParameterEdge(
            "java.lang.String",
            "com.test.TestClass.method",
            0
        );

        // Assert
        assertNotNull(edge);
        assertEquals("member_of", edge.get("edgeType"));
        assertEquals("argument", edge.get("kind"));
        assertEquals(0, edge.get("parameterIndex"));
    }

    @Test
    @DisplayName("Test createCallEdge")
    public void testCreateCallEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createCallEdge(
            "com.test.Caller.callerMethod",
            "com.test.Callee.calleeMethod"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("calls", edge.get("edgeType"));
        assertEquals("com.test.Caller.callerMethod", edge.get("fromFqn"));
        assertEquals("com.test.Callee.calleeMethod", edge.get("toFqn"));
    }

    @Test
    @DisplayName("Test createFieldDependencyEdge with injection type")
    public void testCreateFieldDependencyEdgeWithInjection() {
        // Act
        Map<String, Object> edge = edgeBuilder.createFieldDependencyEdge(
            "com.test.Service",
            "com.test.Controller",
            "autowired",
            "primaryService"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("member_of", edge.get("edgeType"));
        assertEquals("class:autowired", edge.get("kind"));
        assertEquals("primaryService", edge.get("qualifier"));
    }

    @Test
    @DisplayName("Test createFieldDependencyEdge without injection type")
    public void testCreateFieldDependencyEdgeWithoutInjection() {
        // Act
        Map<String, Object> edge = edgeBuilder.createFieldDependencyEdge(
            "com.test.Dependency",
            "com.test.TestClass",
            null,
            null
        );

        // Assert
        assertNotNull(edge);
        assertEquals("class", edge.get("kind"));
        assertFalse(edge.containsKey("qualifier"));
    }

    @Test
    @DisplayName("Test createInheritanceEdge")
    public void testCreateInheritanceEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createInheritanceEdge(
            "com.test.ChildClass",
            "com.test.ParentClass"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("extends", edge.get("edgeType"));
        assertEquals("com.test.ChildClass", edge.get("fromFqn"));
        assertEquals("com.test.ParentClass", edge.get("toFqn"));
    }

    @Test
    @DisplayName("Test createImplementationEdge")
    public void testCreateImplementationEdge() {
        // Act
        Map<String, Object> edge = edgeBuilder.createImplementationEdge(
            "com.test.TestClass",
            "com.test.TestInterface"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("implements", edge.get("edgeType"));
        assertEquals("com.test.TestClass", edge.get("fromFqn"));
        assertEquals("com.test.TestInterface", edge.get("toFqn"));
    }

    @Test
    @DisplayName("Test isPrimitive with primitive types")
    public void testIsPrimitiveWithPrimitives() {
        // Assert
        assertTrue(edgeBuilder.isPrimitive("byte"));
        assertTrue(edgeBuilder.isPrimitive("short"));
        assertTrue(edgeBuilder.isPrimitive("int"));
        assertTrue(edgeBuilder.isPrimitive("long"));
        assertTrue(edgeBuilder.isPrimitive("float"));
        assertTrue(edgeBuilder.isPrimitive("double"));
        assertTrue(edgeBuilder.isPrimitive("boolean"));
        assertTrue(edgeBuilder.isPrimitive("char"));
    }

    @Test
    @DisplayName("Test isPrimitive with wrapper classes")
    public void testIsPrimitiveWithWrappers() {
        // Assert
        assertTrue(edgeBuilder.isPrimitive("java.lang.Byte"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Short"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Integer"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Long"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Float"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Double"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Boolean"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.Character"));
        assertTrue(edgeBuilder.isPrimitive("java.lang.String"));
    }

    @Test
    @DisplayName("Test isPrimitive with custom classes")
    public void testIsPrimitiveWithCustomClasses() {
        // Assert
        assertFalse(edgeBuilder.isPrimitive("com.test.MyClass"));
        assertFalse(edgeBuilder.isPrimitive("java.util.List"));
        assertFalse(edgeBuilder.isPrimitive("java.util.Map"));
    }

    @Test
    @DisplayName("Test isPrimitive with null")
    public void testIsPrimitiveWithNull() {
        // Assert
        assertTrue(edgeBuilder.isPrimitive(null));
    }

    @Test
    @DisplayName("Test createDependencyEdgeIfNotPrimitive with primitive type")
    public void testCreateDependencyEdgeIfNotPrimitiveWithPrimitive() {
        // Act
        Map<String, Object> edge = edgeBuilder.createDependencyEdgeIfNotPrimitive(
            "int",
            "com.test.TestClass",
            "return"
        );

        // Assert - should return null for primitive types
        assertNull(edge);

        // No edge should be added
        assertEquals(0, context.getEdges().size());
    }

    @Test
    @DisplayName("Test createDependencyEdgeIfNotPrimitive with custom type")
    public void testCreateDependencyEdgeIfNotPrimitiveWithCustomType() {
        // Act
        Map<String, Object> edge = edgeBuilder.createDependencyEdgeIfNotPrimitive(
            "com.test.MyClass",
            "com.test.TestClass",
            "return"
        );

        // Assert
        assertNotNull(edge);
        assertEquals("member_of", edge.get("edgeType"));
        assertEquals("return", edge.get("kind"));

        // Edge should be added to context
        assertEquals(1, context.getEdges().size());
    }

    @Test
    @DisplayName("Test multiple edges are added to context")
    public void testMultipleEdgesAddedToContext() {
        // Act
        edgeBuilder.createMemberEdge("method1", "Class1", "method");
        edgeBuilder.createCallEdge("Class1.method1", "Class2.method2");
        edgeBuilder.createInheritanceEdge("Class2", "Class3");

        // Assert
        List<Map<String, Object>> edges = context.getEdges();
        assertEquals(3, edges.size());
    }

    @Test
    @DisplayName("Test field dependency with @Resource injection")
    public void testFieldDependencyWithResource() {
        // Act
        Map<String, Object> edge = edgeBuilder.createFieldDependencyEdge(
            "javax.sql.DataSource",
            "com.test.Repository",
            "resource",
            null
        );

        // Assert
        assertNotNull(edge);
        assertEquals("class:resource", edge.get("kind"));
    }

    @Test
    @DisplayName("Test field dependency with @Inject injection")
    public void testFieldDependencyWithInject() {
        // Act
        Map<String, Object> edge = edgeBuilder.createFieldDependencyEdge(
            "com.test.Service",
            "com.test.Controller",
            "inject",
            null
        );

        // Assert
        assertNotNull(edge);
        assertEquals("class:inject", edge.get("kind"));
    }

    @Test
    @DisplayName("Test parameter edge with multiple parameters")
    public void testParameterEdgeWithMultipleParameters() {
        // Act
        edgeBuilder.createParameterEdge("java.lang.String", "method", 0);
        edgeBuilder.createParameterEdge("int", "method", 1);
        edgeBuilder.createParameterEdge("boolean", "method", 2);

        // Assert
        List<Map<String, Object>> edges = context.getEdges();
        assertEquals(3, edges.size());

        assertEquals(0, edges.get(0).get("parameterIndex"));
        assertEquals(1, edges.get(1).get("parameterIndex"));
        assertEquals(2, edges.get(2).get("parameterIndex"));
    }

    @Test
    @DisplayName("Test edge contains all required fields")
    public void testEdgeContainsAllRequiredFields() {
        // Act
        Map<String, Object> edge = edgeBuilder.createCallEdge("from", "to");

        // Assert
        assertTrue(edge.containsKey("edgeType"));
        assertTrue(edge.containsKey("fromFqn"));
        assertTrue(edge.containsKey("toFqn"));
        assertEquals(3, edge.size());
    }

    @Test
    @DisplayName("Test builder initialization with context")
    public void testBuilderInitialization() {
        // Assert
        assertNotNull(edgeBuilder);
    }
}
