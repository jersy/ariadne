package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Lazy annotation.
 *
 * <p>Indicates that a bean should be lazily initialized.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class LazyAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(LazyAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.LAZY.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setLazy(true);

        logger.info("[LAZY_HANDLER] @Lazy detected on class {}",
            context.getClassName());
    }

    @Override
    public int getPriority() {
        return 55; // Medium priority for initialization configuration
    }
}
