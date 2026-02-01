package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Scope annotation.
 *
 * <p>Handles the @Scope annotation at class level, processing both
 * String value and enum value attributes.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ScopeAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ScopeAnnotationHandler.class);

    private AnnotationVisitor parentVisitor;

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.SCOPE.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.debug("[SCOPE_HANDLER] @Scope detected on class {}",
            context.getClassName());
    }

    /**
     * Creates an AnnotationVisitor to process @Scope attributes.
     *
     * @param parentAv The parent annotation visitor
     * @param context The analysis context
     * @return AnnotationVisitor for processing scope attributes
     */
    public AnnotationVisitor createAttributeVisitor(
        AnnotationVisitor parentAv,
        AnalysisContext context
    ) {
        this.parentVisitor = parentAv;

        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    context.setSpringScope(value.toString());
                    logger.info("[SCOPE] Class {} has @Scope with value: {}",
                        context.getClassName(), value);
                }
                super.visit(name, value);
            }

            @Override
            public void visitEnum(String name, String descriptor, String value) {
                if ("value".equals(name)) {
                    context.setSpringScope(value);
                    logger.info("[SCOPE] Class {} has @Scope with enum value: {}",
                        context.getClassName(), value);
                }
                super.visitEnum(name, descriptor, value);
            }
        };
    }

    @Override
    public int getPriority() {
        return 60; // Medium priority for scope configuration
    }
}
