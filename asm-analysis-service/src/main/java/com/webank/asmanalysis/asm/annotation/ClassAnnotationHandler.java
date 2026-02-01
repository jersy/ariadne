package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;

/**
 * Interface for handling class-level annotations.
 *
 * <p>Implementations process annotations that appear on classes (e.g., @Service, @Component).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public interface ClassAnnotationHandler extends AnnotationHandler {
    /**
     * Handles a class-level annotation.
     *
     * @param context The annotation processing context
     */
    void handleClass(ClassAnnotationContext context);
}
