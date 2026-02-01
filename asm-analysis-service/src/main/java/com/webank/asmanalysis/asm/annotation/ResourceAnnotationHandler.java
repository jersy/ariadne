package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Resource annotation.
 *
 * <p>Handles javax.annotation @Resource annotation at field level.
 * Standard Java resource injection annotation (JSR-250).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ResourceAnnotationHandler implements FieldAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ResourceAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.RESOURCE.equals(descriptor);
    }

    @Override
    public void handleField(FieldAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        logger.debug("[RESOURCE_FIELD_HANDLER] @Resource detected on field {}.{}",
            context.getClassName(), context.getFieldName());
    }

    @Override
    public int getPriority() {
        return 91; // High priority for standard resource injection
    }
}
