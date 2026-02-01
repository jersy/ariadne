package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;

/**
 * Context for field-level annotation processing.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class FieldAnnotationContext {
    private final AnalysisContext analysisContext;
    private final String descriptor;
    private final boolean visible;
    private final String className;
    private final String fieldName;

    public FieldAnnotationContext(
        AnalysisContext analysisContext,
        String descriptor,
        boolean visible,
        String className,
        String fieldName
    ) {
        this.analysisContext = analysisContext;
        this.descriptor = descriptor;
        this.visible = visible;
        this.className = className;
        this.fieldName = fieldName;
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

    public String getFieldName() {
        return fieldName;
    }
}
