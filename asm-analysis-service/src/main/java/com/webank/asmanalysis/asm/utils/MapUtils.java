package com.webank.asmanalysis.asm.utils;

import java.util.HashMap;
import java.util.Map;

/**
 * Utility class for Map operations.
 *
 * <p>Provides common methods to reduce code duplication when working with Maps.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public final class MapUtils {

    private MapUtils() {
        // Utility class - prevent instantiation
    }

    /**
     * Creates a new HashMap for edge or node properties.
     *
     * @return a new HashMap instance
     */
    public static Map<String, Object> newHashMap() {
        return new HashMap<>();
    }

    /**
     * Creates a new HashMap with specified initial capacity.
     *
     * @param initialCapacity the initial capacity
     * @return a new HashMap instance
     */
    public static Map<String, Object> newHashMap(int initialCapacity) {
        return new HashMap<>(initialCapacity);
    }

    /**
     * Puts a value into a map if the value is not null.
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
     * Puts a value into a map if the value is not null and not empty (for strings).
     *
     * @param map the map to modify
     * @param key the key
     * @param value the value
     */
    public static void putIfNotNullOrEmpty(Map<String, Object> map, String key, String value) {
        if (value != null && !value.isEmpty()) {
            map.put(key, value);
        }
    }

    /**
     * Puts a value into a map if the condition is true.
     *
     * @param map the map to modify
     * @param key the key
     * @param value the value
     * @param condition the condition to check
     * @param <K> the key type
     * @param <V> the value type
     */
    public static <K, V> void putIf(Map<K, V> map, K key, V value, boolean condition) {
        if (condition) {
            map.put(key, value);
        }
    }

    /**
     * Gets a value from a map as a String, returning null if not present or wrong type.
     *
     * @param map the map to read from
     * @param key the key
     * @return the value as a String, or null
     */
    public static String getString(Map<String, Object> map, String key) {
        Object value = map.get(key);
        if (value instanceof String) {
            return (String) value;
        }
        return value != null ? value.toString() : null;
    }

    /**
     * Gets a value from a map as an Integer, returning null if not present or wrong type.
     *
     * @param map the map to read from
     * @param key the key
     * @return the value as an Integer, or null
     */
    public static Integer getInteger(Map<String, Object> map, String key) {
        Object value = map.get(key);
        if (value instanceof Integer) {
            return (Integer) value;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return null;
    }

    /**
     * Gets a value from a map as a Boolean, returning null if not present or wrong type.
     *
     * @param map the map to read from
     * @param key the key
     * @return the value as a Boolean, or null
     */
    public static Boolean getBoolean(Map<String, Object> map, String key) {
        Object value = map.get(key);
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        return null;
    }

    /**
     * Gets the attributes map from a node, creating it if necessary.
     *
     * @param node the node map
     * @return the attributes map
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> getOrCreateAttributes(Map<String, Object> node) {
        Map<String, Object> attributes = (Map<String, Object>) node.get("attributes");
        if (attributes == null) {
            attributes = newHashMap();
            node.put("attributes", attributes);
        }
        return attributes;
    }

    /**
     * Copies all entries from source map to target map if values are not null.
     *
     * @param target the target map
     * @param source the source map
     */
    public static void putAllIfNotNull(Map<String, Object> target, Map<String, Object> source) {
        if (source == null) {
            return;
        }
        for (Map.Entry<String, Object> entry : source.entrySet()) {
            if (entry.getValue() != null) {
                target.put(entry.getKey(), entry.getValue());
            }
        }
    }
}
