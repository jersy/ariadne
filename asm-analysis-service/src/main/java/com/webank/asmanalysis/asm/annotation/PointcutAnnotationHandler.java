package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Pointcut annotation.
 *
 * <p>Handles AspectJ @Pointcut annotation to identify pointcut definitions.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class PointcutAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(PointcutAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.POINTCUT.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark as pointcut definition
        methodNode.put("isPointcut", true);
        methodNode.put("aopPointcut", true);

        logger.info("[POINTCUT_HANDLER] @Pointcut detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 78; // High priority for AOP configuration
    }
}
