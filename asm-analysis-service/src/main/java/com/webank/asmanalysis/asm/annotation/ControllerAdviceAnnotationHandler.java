package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @ControllerAdvice annotation.
 *
 * <p>Handles Spring @ControllerAdvice annotation for global exception handling
 * and cross-cutting concerns in REST controllers.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ControllerAdviceAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ControllerAdviceAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.CONTROLLER_ADVICE.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.info("[CONTROLLER_ADVICE_HANDLER] @ControllerAdvice detected on class {}",
            context.getClassName());
    }

    @Override
    public int getPriority() {
        return 98; // Very high priority for global controller configuration
    }
}
