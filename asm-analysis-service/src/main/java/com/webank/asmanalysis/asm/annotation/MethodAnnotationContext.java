package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;
import java.util.Map;

/**
 * Context for method-level annotation processing.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MethodAnnotationContext {
    private final AnalysisContext analysisContext;
    private final String descriptor;
    private final boolean visible;
    private final Map<String, Object> methodNode;

    public MethodAnnotationContext(
        AnalysisContext analysisContext,
        String descriptor,
        boolean visible,
        Map<String, Object> methodNode
    ) {
        this.analysisContext = analysisContext;
        this.descriptor = descriptor;
        this.visible = visible;
        this.methodNode = methodNode;
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

    public Map<String, Object> getMethodNode() {
        return methodNode;
    }

    /**
     * Gets the method FQN from the method node.
     */
    public String getMethodFqn() {
        return (String) methodNode.get("fqn");
    }
}
