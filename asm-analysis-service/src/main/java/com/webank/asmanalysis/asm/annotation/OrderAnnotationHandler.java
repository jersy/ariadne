package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Order annotation.
 *
 * <p>Handles Spring @Order annotation at both class and method level.
 * Used to specify ordering for AOP aspects and other components.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class OrderAnnotationHandler implements ClassAnnotationHandler, MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(OrderAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.ORDER.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.debug("[ORDER_CLASS_HANDLER] @Order detected on class {}",
            context.getClassName());
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark method as having order specification
        methodNode.put("hasOrder", true);

        logger.debug("[ORDER_METHOD_HANDLER] @Order detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 50; // Medium priority for ordering configuration
    }
}
