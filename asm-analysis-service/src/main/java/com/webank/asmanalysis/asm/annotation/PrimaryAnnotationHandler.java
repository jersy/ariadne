package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Primary annotation.
 *
 * <p>Marks a bean as primary when multiple candidates are available.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class PrimaryAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(PrimaryAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.PRIMARY.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setPrimary(true);

        logger.info("[PRIMARY_HANDLER] @Primary detected on class {}",
            context.getClassName());
    }

    @Override
    public int getPriority() {
        return 65; // Medium-high priority for bean selection configuration
    }
}
