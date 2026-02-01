package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Qualifier annotation.
 *
 * <p>Handles Spring @Qualifier annotation at field level.
 * Used to disambiguate when multiple beans of the same type exist.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class QualifierAnnotationHandler implements FieldAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(QualifierAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.QUALIFIER.equals(descriptor);
    }

    @Override
    public void handleField(FieldAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        logger.debug("[QUALIFIER_FIELD_HANDLER] @Qualifier detected on field {}.{}",
            context.getClassName(), context.getFieldName());
    }

    @Override
    public int getPriority() {
        return 90; // High priority for dependency injection disambiguation
    }
}
