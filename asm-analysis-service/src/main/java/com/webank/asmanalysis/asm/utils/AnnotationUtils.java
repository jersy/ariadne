package com.webank.asmanalysis.asm.utils;

import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;
import java.util.function.BiConsumer;

/**
 * Utility class for annotation processing operations.
 *
 * <p>Provides common methods to reduce code duplication in annotation handlers.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public final class AnnotationUtils {

    private static final Logger logger = LoggerFactory.getLogger(AnnotationUtils.class);

    private AnnotationUtils() {
        // Utility class - prevent instantiation
    }

    /**
     * Creates a new HashMap for storing node properties.
     *
     * @param <K> the key type
     * @param <V> the value type
     * @return a new HashMap instance
     */
    public static <K, V> Map<K, V> newMap() {
        return new HashMap<>();
    }

    /**
     * Creates a new HashMap with initial capacity.
     *
     * @param <K> the key type
     * @param <V> the value type
     * @param capacity the initial capacity
     * @return a new HashMap instance
     */
    public static <K, V> Map<K, V> newMap(int capacity) {
        return new HashMap<>(capacity);
    }

    /**
     * Creates an AnnotationVisitor for processing string-valued annotation attributes.
     *
     * @param parentAv the parent annotation visitor
     * @param attributeName the name of the attribute to extract
     * @param valueConsumer consumer that receives the extracted value
     * @return an AnnotationVisitor that processes the attribute
     */
    public static AnnotationVisitor createStringAttributeVisitor(
        AnnotationVisitor parentAv,
        String attributeName,
        BiConsumer<String, Object> valueConsumer
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if (attributeName.equals(name)) {
                    valueConsumer.accept(name, value);
                }
                super.visit(name, value);
            }
        };
    }

    /**
     * Creates an AnnotationVisitor for processing string-valued annotation attributes with logging.
     *
     * @param parentAv the parent annotation visitor
     * @param attributeName the name of the attribute to extract
     * @param valueConsumer consumer that receives the extracted value
     * @param logPrefix the prefix for log messages
     * @param logger the logger to use
     * @return an AnnotationVisitor that processes the attribute
     */
    public static AnnotationVisitor createStringAttributeVisitorWithLogging(
        AnnotationVisitor parentAv,
        String attributeName,
        BiConsumer<String, Object> valueConsumer,
        String logPrefix,
        Logger logger
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if (attributeName.equals(name)) {
                    valueConsumer.accept(name, value);
                    logger.info("[{}] Attribute {} = {}", logPrefix, attributeName, value);
                }
                super.visit(name, value);
            }
        };
    }

    /**
     * Creates an AnnotationVisitor for processing array-valued annotation attributes.
     *
     * @param parentAv the parent annotation visitor
     * @param attributeName the name of the attribute to extract
     * @param arrayConsumer consumer that receives the array values
     * @return an AnnotationVisitor that processes the attribute
     */
    public static AnnotationVisitor createArrayAttributeVisitor(
        AnnotationVisitor parentAv,
        String attributeName,
        BiConsumer<String, Object[]> arrayConsumer
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            private final java.util.List<Object> values = new java.util.ArrayList<>();

            @Override
            public AnnotationVisitor visitArray(String name) {
                if (attributeName.equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9) {
                        @Override
                        public void visit(String name, Object value) {
                            values.add(value);
                            super.visit(name, value);
                        }
                    };
                }
                return super.visitArray(name);
            }

            @Override
            public void visitEnd() {
                if (!values.isEmpty()) {
                    arrayConsumer.accept(attributeName, values.toArray());
                }
                super.visitEnd();
            }
        };
    }

    /**
     * Safely puts a value into a map if the value is not null.
     *
     * @param map the map to modify
     * @param key the key
     * @param value the value
     * @param <K> the key type
     * @param <V> the value type
     */
    public static <K, V> void putIfNotNull(Map<K, V> map, K key, V value) {
        if (value != null) {
            map.put(key, value);
        }
    }

    /**
     * Safely puts a value into a nested attributes map if the value is not null.
     *
     * @param node the node map containing the attributes
     * @param key the key in the attributes map
     * @param value the value
     */
    @SuppressWarnings("unchecked")
    public static void putAttributeIfNotNull(Map<String, Object> node, String key, Object value) {
        if (value != null) {
            Map<String, Object> attributes = getOrCreateAttributes(node);
            attributes.put(key, value);
        }
    }

    /**
     * Gets or creates the attributes map in a node.
     *
     * @param node the node map
     * @return the attributes map
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> getOrCreateAttributes(Map<String, Object> node) {
        Map<String, Object> attributes = (Map<String, Object>) node.get("attributes");
        if (attributes == null) {
            attributes = newMap();
            node.put("attributes", attributes);
        }
        return attributes;
    }

    /**
     * Checks if a string is null or empty.
     *
     * @param str the string to check
     * @return true if the string is null or empty
     */
    public static boolean isNullOrEmpty(String str) {
        return str == null || str.isEmpty();
    }

    /**
     * Checks if a string is not null and not empty.
     *
     * @param str the string to check
     * @return true if the string is not null and not empty
     */
    public static boolean isNotEmpty(String str) {
        return str != null && !str.isEmpty();
    }

    /**
     * Extracts the simple class name from a fully qualified name.
     *
     * @param fqn the fully qualified class name
     * @return the simple class name, or the input if no dot is found
     */
    public static String getSimpleName(String fqn) {
        if (isNullOrEmpty(fqn)) {
            return fqn;
        }
        int lastDot = fqn.lastIndexOf('.');
        return lastDot > 0 ? fqn.substring(lastDot + 1) : fqn;
    }

    /**
     * Extracts the package name from a fully qualified name.
     *
     * @param fqn the fully qualified class name
     * @return the package name, or empty string if no dot is found
     */
    public static String getPackageName(String fqn) {
        if (isNullOrEmpty(fqn)) {
            return "";
        }
        int lastDot = fqn.lastIndexOf('.');
        return lastDot > 0 ? fqn.substring(0, lastDot) : "";
    }

    /**
     * Converts ASM internal name to FQN.
     * Example: com/example/MyClass -> com.example.MyClass
     *
     * @param internalName the ASM internal name
     * @return the fully qualified name
     */
    public static String internalNameToFqn(String internalName) {
        if (isNullOrEmpty(internalName)) {
            return internalName;
        }
        return internalName.replace('/', '.');
    }

    /**
     * Converts FQN to ASM internal name.
     * Example: com.example.MyClass -> com/example/MyClass
     *
     * @param fqn the fully qualified name
     * @return the ASM internal name
     */
    public static String fqnToInternalName(String fqn) {
        if (isNullOrEmpty(fqn)) {
            return fqn;
        }
        return fqn.replace('.', '/');
    }
}
