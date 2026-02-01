package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @DependsOn annotation.
 *
 * <p>Handles Spring @DependsOn annotation to track bean dependencies.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class DependsOnAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(DependsOnAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.DEPENDS_ON.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark method as having dependencies
        methodNode.put("hasDependsOn", true);

        logger.debug("[DEPENDS_ON_HANDLER] @DependsOn detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 68; // Medium-high priority for dependency tracking
    }
}
