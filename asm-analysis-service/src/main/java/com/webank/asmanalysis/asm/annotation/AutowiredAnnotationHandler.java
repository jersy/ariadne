package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Autowired annotation.
 *
 * <p>Handles Spring @Autowired annotation at field level.
 * Marks fields for dependency injection.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class AutowiredAnnotationHandler implements FieldAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(AutowiredAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.AUTOWIRED.equals(descriptor);
    }

    @Override
    public void handleField(FieldAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        // Record that this field has @Autowired annotation
        logger.debug("[AUTOWIRED_FIELD_HANDLER] @Autowired detected on field {}.{}",
            context.getClassName(), context.getFieldName());
    }

    @Override
    public int getPriority() {
        return 95; // High priority for dependency injection
    }
}
