package com.webank.asmanalysis.asm.annotation;

/**
 * Interface for handling method-level annotations.
 *
 * <p>Implementations process annotations that appear on methods (e.g., @Transactional, @Async).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public interface MethodAnnotationHandler extends AnnotationHandler {
    /**
     * Handles a method-level annotation.
     *
     * @param context The annotation processing context
     */
    void handleMethod(MethodAnnotationContext context);
}
