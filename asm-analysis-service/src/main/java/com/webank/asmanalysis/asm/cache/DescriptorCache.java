package com.webank.asmanalysis.asm.cache;

import org.objectweb.asm.Type;

import java.util.concurrent.ConcurrentHashMap;

/**
 * Cache for ASM descriptor conversions to improve performance.
 *
 * <p>This class caches the results of expensive descriptor-to-class-name conversions,
 * which are frequently performed during bytecode analysis. Using a cache can significantly
 * improve performance when analyzing large codebases with many repeated type references.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public final class DescriptorCache {

    private static final DescriptorCache INSTANCE = new DescriptorCache();

    // Cache for descriptor to class name conversions
    private final ConcurrentHashMap<String, String> descriptorToClassNameCache;

    // Cache for class name to internal name conversions
    private final ConcurrentHashMap<String, String> classNameToInternalNameCache;

    // Cache for descriptor to simple name conversions
    private final ConcurrentHashMap<String, String> descriptorToSimpleNameCache;

    // Statistics
    private volatile long cacheHits;
    private volatile long cacheMisses;

    private DescriptorCache() {
        this.descriptorToClassNameCache = new ConcurrentHashMap<>(256);
        this.classNameToInternalNameCache = new ConcurrentHashMap<>(256);
        this.descriptorToSimpleNameCache = new ConcurrentHashMap<>(256);
        this.cacheHits = 0;
        this.cacheMisses = 0;
    }

    /**
     * Gets the singleton instance of the descriptor cache.
     *
     * @return the descriptor cache instance
     */
    public static DescriptorCache getInstance() {
        return INSTANCE;
    }

    /**
     * Converts a JVM descriptor to a class name, using cache if available.
     *
     * @param descriptor the JVM descriptor (e.g., "Ljava/lang/String;")
     * @return the class name (e.g., "java.lang.String"), or null if primitive
     */
    public String descriptorToClassName(String descriptor) {
        if (descriptor == null) {
            return null;
        }

        // Check cache first
        String cached = descriptorToClassNameCache.get(descriptor);
        if (cached != null) {
            cacheHits++;
            return cached;
        }

        cacheMisses++;

        // Not in cache, compute and store
        String className = computeDescriptorToClassName(descriptor);
        if (className != null) {
            descriptorToClassNameCache.put(descriptor, className);
        }

        return className;
    }

    /**
     * Converts a class name to ASM internal name, using cache if available.
     *
     * @param className the fully qualified class name (e.g., "java.lang.String")
     * @return the internal name (e.g., "java/lang/String")
     */
    public String classNameToInternalName(String className) {
        if (className == null) {
            return null;
        }

        // Check cache first
        String cached = classNameToInternalNameCache.get(className);
        if (cached != null) {
            cacheHits++;
            return cached;
        }

        cacheMisses++;

        // Not in cache, compute and store
        String internalName = className.replace('.', '/');
        classNameToInternalNameCache.put(className, internalName);
        return internalName;
    }

    /**
     * Extracts the simple class name from a descriptor, using cache if available.
     *
     * @param descriptor the JVM descriptor
     * @return the simple class name (e.g., "String")
     */
    public String descriptorToSimpleName(String descriptor) {
        if (descriptor == null) {
            return null;
        }

        // Check cache first
        String cached = descriptorToSimpleNameCache.get(descriptor);
        if (cached != null) {
            cacheHits++;
            return cached;
        }

        cacheMisses++;

        // Not in cache, compute and store
        String className = descriptorToClassName(descriptor);
        if (className != null) {
            int lastDot = className.lastIndexOf('.');
            String simpleName = lastDot > 0 ? className.substring(lastDot + 1) : className;
            descriptorToSimpleNameCache.put(descriptor, simpleName);
            return simpleName;
        }

        return null;
    }

    /**
     * Computes the class name from a descriptor.
     *
     * @param descriptor the JVM descriptor
     * @return the class name, or null for primitive types
     */
    private String computeDescriptorToClassName(String descriptor) {
        if (descriptor == null) {
            return null;
        }

        // Array types
        if (descriptor.startsWith("[")) {
            return Type.getType(descriptor).getClassName();
        }

        // Object types: Ljava/lang/String;
        if (descriptor.startsWith("L") && descriptor.endsWith(";")) {
            return descriptor.substring(1, descriptor.length() - 1).replace('/', '.');
        }

        // Primitive types - return null
        return null;
    }

    /**
     * Clears all caches.
     *
     * <p>This can be useful between analysis runs to free memory.
     */
    public void clear() {
        descriptorToClassNameCache.clear();
        classNameToInternalNameCache.clear();
        descriptorToSimpleNameCache.clear();
        resetStatistics();
    }

    /**
     * Resets the cache statistics.
     */
    public void resetStatistics() {
        cacheHits = 0;
        cacheMisses = 0;
    }

    /**
     * Gets the cache hit rate.
     *
     * @return the hit rate as a percentage (0-100), or 0 if no requests
     */
    public double getHitRate() {
        long total = cacheHits + cacheMisses;
        return total > 0 ? (cacheHits * 100.0 / total) : 0.0;
    }

    /**
     * Gets the number of cache hits.
     *
     * @return the cache hit count
     */
    public long getCacheHits() {
        return cacheHits;
    }

    /**
     * Gets the number of cache misses.
     *
     * @return the cache miss count
     */
    public long getCacheMisses() {
        return cacheMisses;
    }

    /**
     * Gets the size of the descriptor-to-class-name cache.
     *
     * @return the cache size
     */
    public int getDescriptorCacheSize() {
        return descriptorToClassNameCache.size();
    }

    /**
     * Gets the size of the class-name-to-internal-name cache.
     *
     * @return the cache size
     */
    public int getInternalNameCacheSize() {
        return classNameToInternalNameCache.size();
    }

    /**
     * Gets statistics about the cache.
     *
     * @return a string containing cache statistics
     */
    public String getStatistics() {
        return String.format(
            "DescriptorCache[hits=%d, misses=%d, hitRate=%.2f%%, descriptorCache=%d, internalNameCache=%d]",
            cacheHits,
            cacheMisses,
            getHitRate(),
            getDescriptorCacheSize(),
            getInternalNameCacheSize()
        );
    }

    /**
     * Resets the singleton instance (mainly for testing purposes).
     */
    public static void reset() {
        INSTANCE.clear();
    }
}
