package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;

/**
 * Context for class-level annotation processing.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ClassAnnotationContext {
    private final AnalysisContext analysisContext;
    private final String descriptor;
    private final boolean visible;
    private final String className;

    public ClassAnnotationContext(
        AnalysisContext analysisContext,
        String descriptor,
        boolean visible,
        String className
    ) {
        this.analysisContext = analysisContext;
        this.descriptor = descriptor;
        this.visible = visible;
        this.className = className;
    }

    public AnalysisContext getAnalysisContext() {
        return analysisContext;
    }

    public String getDescriptor() {
        return descriptor;
    }

    public boolean isVisible() {
        return visible;
    }

    public String getClassName() {
        return className;
    }
}
