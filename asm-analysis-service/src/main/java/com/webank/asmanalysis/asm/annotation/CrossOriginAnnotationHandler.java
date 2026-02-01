package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @CrossOrigin annotation.
 *
 * <p>Handles Spring @CrossOrigin annotation for CORS configuration.
 * Can be applied at both class and method level.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class CrossOriginAnnotationHandler implements ClassAnnotationHandler, MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(CrossOriginAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.CROSS_ORIGIN.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.debug("[CROSS_ORIGIN_CLASS_HANDLER] @CrossOrigin detected on class {}",
            context.getClassName());
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark method as having CORS configuration
        methodNode.put("hasCrossOrigin", true);

        logger.debug("[CROSS_ORIGIN_METHOD_HANDLER] @CrossOrigin detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 58; // Medium priority for CORS configuration
    }
}
