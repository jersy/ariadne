package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Inject annotation.
 *
 * <p>Handles javax.inject @Inject annotation at field level.
 * Standard Java dependency injection annotation (JSR-330).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class InjectAnnotationHandler implements FieldAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(InjectAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.INJECT.equals(descriptor);
    }

    @Override
    public void handleField(FieldAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        logger.debug("[INJECT_FIELD_HANDLER] @Inject detected on field {}.{}",
            context.getClassName(), context.getFieldName());
    }

    @Override
    public int getPriority() {
        return 92; // High priority for standard dependency injection
    }
}
