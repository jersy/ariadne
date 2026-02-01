package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Aspect annotation.
 *
 * <p>Handles both Spring Framework @Aspect and AspectJ @Aspect annotations.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class AspectAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(AspectAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.SPRING_ASPECT.equals(descriptor) ||
               AnnotationConstants.ASPECTJ_ASPECT.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setAspect(true);
        analysisContext.setNeedsProxy(true);

        String aspectType = AnnotationConstants.SPRING_ASPECT.equals(context.getDescriptor())
            ? "Spring" : "AspectJ";

        logger.info("[ASPECT_HANDLER] @Aspect ({}) detected on class {}",
            aspectType, context.getClassName());
    }

    @Override
    public int getPriority() {
        return 95; // Very high priority for AOP configuration
    }
}
