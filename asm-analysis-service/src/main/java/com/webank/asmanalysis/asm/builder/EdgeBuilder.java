package com.webank.asmanalysis.asm.builder;

import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

/**
 * Builder class for creating dependency edges in the call graph.
 *
 * <p>This class provides a fluent interface for constructing edges
 * between nodes (classes, methods) with proper edge type classification.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class EdgeBuilder {
    private static final Logger logger = LoggerFactory.getLogger(EdgeBuilder.class);

    private final AnalysisContext context;

    public EdgeBuilder(AnalysisContext context) {
        this.context = context;
    }

    /**
     * Creates a member_of edge.
     *
     * @param fromFqn The source FQN (method/field)
     * @param toFqn The target FQN (class)
     * @param kind The kind of member (method/field)
     * @return The created edge map
     */
    public Map<String, Object> createMemberEdge(String fromFqn, String toFqn, String kind) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "member_of");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", kind);

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created member edge: {} -> {}", fromFqn, toFqn);

        return edge;
    }

    /**
     * Creates a method return edge.
     *
     * @param fromFqn The return type FQN
     * @param toFqn The method FQN
     * @return The created edge map
     */
    public Map<String, Object> createReturnEdge(String fromFqn, String toFqn) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "member_of");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", "return");

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created return edge: {} -> {}", fromFqn, toFqn);

        return edge;
    }

    /**
     * Creates a method parameter edge.
     *
     * @param fromFqn The parameter type FQN
     * @param toFqn The method FQN
     * @param parameterIndex The parameter index (0-based)
     * @return The created edge map
     */
    public Map<String, Object> createParameterEdge(String fromFqn, String toFqn, int parameterIndex) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "member_of");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", "argument");
        edge.put("parameterIndex", parameterIndex);

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created parameter edge: {} -> {} (index: {})",
            fromFqn, toFqn, parameterIndex);

        return edge;
    }

    /**
     * Creates a method call edge.
     *
     * @param fromFqn The caller method FQN
     * @param toFqn The callee method FQN
     * @return The created edge map
     */
    public Map<String, Object> createCallEdge(String fromFqn, String toFqn) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "calls");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created call edge: {} -> {}", fromFqn, toFqn);

        return edge;
    }

    /**
     * Creates a field dependency edge.
     *
     * @param fromFqn The field type FQN
     * @param toFqn The class FQN containing the field
     * @param injectionType The injection type (autowired/inject/resource/class)
     * @param qualifier The qualifier value (optional)
     * @return The created edge map
     */
    public Map<String, Object> createFieldDependencyEdge(
        String fromFqn,
        String toFqn,
        String injectionType,
        String qualifier
    ) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "member_of");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", injectionType != null && !injectionType.isEmpty() ? "class:" + injectionType : "class");

        if (qualifier != null && !qualifier.isEmpty()) {
            edge.put("qualifier", qualifier);
        }

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created field dependency edge: {} -> {} (type: {}, qualifier: {})",
            fromFqn, toFqn, injectionType, qualifier);

        return edge;
    }

    /**
     * Creates an inheritance edge.
     *
     * @param fromFqn The child class FQN
     * @param toFqn The parent class FQN
     * @return The created edge map
     */
    public Map<String, Object> createInheritanceEdge(String fromFqn, String toFqn) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "inheritance");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", "extends");

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created inheritance edge: {} extends {}", fromFqn, toFqn);

        return edge;
    }

    /**
     * Creates an interface implementation edge.
     *
     * @param fromFqn The class FQN
     * @param toFqn The interface FQN
     * @return The created edge map
     */
    public Map<String, Object> createImplementationEdge(String fromFqn, String toFqn) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "inheritance");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", "implements");

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created implementation edge: {} implements {}", fromFqn, toFqn);

        return edge;
    }

    /**
     * Checks if a type is primitive.
     *
     * @param typeName The type name to check
     * @return true if the type is primitive or a wrapper class
     */
    public boolean isPrimitive(String typeName) {
        if (typeName == null) {
            return true;
        }

        // Check for common primitive types and their wrapper classes
        return typeName.equals("byte") || typeName.equals("short") ||
               typeName.equals("int") || typeName.equals("long") ||
               typeName.equals("float") || typeName.equals("double") ||
               typeName.equals("boolean") || typeName.equals("char") ||
               typeName.equals("java.lang.Byte") || typeName.equals("java.lang.Short") ||
               typeName.equals("java.lang.Integer") || typeName.equals("java.lang.Long") ||
               typeName.equals("java.lang.Float") || typeName.equals("java.lang.Double") ||
               typeName.equals("java.lang.Boolean") || typeName.equals("java.lang.Character") ||
               typeName.equals("java.lang.String");
    }

    /**
     * Creates a dependency edge only if the type is not primitive.
     *
     * @param fromFqn The source FQN
     * @param toFqn The target FQN
     * @param kind The edge kind
     * @return The created edge, or null if the type is primitive
     */
    public Map<String, Object> createDependencyEdgeIfNotPrimitive(
        String fromFqn,
        String toFqn,
        String kind
    ) {
        if (isPrimitive(fromFqn)) {
            return null;
        }

        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "member_of");
        edge.put("fromFqn", fromFqn);
        edge.put("toFqn", toFqn);
        edge.put("kind", kind);

        context.addEdge(edge);
        logger.debug("[EDGE_BUILDER] Created dependency edge: {} -> {}", fromFqn, toFqn);

        return edge;
    }
}
