package com.webank.asmanalysis.asm.annotation;

/**
 * Interface for handling field-level annotations.
 *
 * <p>Implementations process annotations that appear on fields (e.g., @Autowired, @Value).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public interface FieldAnnotationHandler extends AnnotationHandler {
    /**
     * Handles a field-level annotation.
     *
     * @param context The annotation processing context
     */
    void handleField(FieldAnnotationContext context);
}
