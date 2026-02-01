package com.webank.asmanalysis.asm.annotation;

/**
 * Base interface for annotation handlers.
 *
 * <p>All annotation-specific handlers must implement this interface to participate
 * in the strategy pattern-based annotation processing.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public interface AnnotationHandler {
    /**
     * Checks if this handler can process the given annotation descriptor.
     *
     * @param descriptor The JVM annotation descriptor (e.g., "Lorg/springframework/stereotype/Service;")
     * @return true if this handler can process the annotation
     */
    boolean canHandle(String descriptor);

    /**
     * Gets the priority of this handler.
     * Higher values indicate higher priority. Handlers with higher priority
     * are checked first.
     *
     * @return The priority value (default: 0)
     */
    default int getPriority() {
        return 0;
    }
}
