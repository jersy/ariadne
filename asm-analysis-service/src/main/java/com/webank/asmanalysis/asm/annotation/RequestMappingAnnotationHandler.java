package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @RequestMapping annotation.
 *
 * <p>Processes class-level @RequestMapping to extract base path and HTTP method.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class RequestMappingAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(RequestMappingAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.REQUEST_MAPPING.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.debug("[REQUEST_MAPPING_HANDLER] @RequestMapping detected on class {}",
            context.getClassName());
    }

    /**
     * Creates an AnnotationVisitor to process @RequestMapping attributes.
     *
     * @param parentAv The parent annotation visitor
     * @param context The analysis context
     * @return AnnotationVisitor for processing request mapping attributes
     */
    public AnnotationVisitor createAttributeVisitor(
        AnnotationVisitor parentAv,
        AnalysisContext context
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name) || "path".equals(name)) {
                    context.setClassBasePath(value.toString());
                    logger.info("[REQUEST_MAPPING] Class {} has base path: {}",
                        context.getClassName(), value);
                } else if ("method".equals(name)) {
                    context.setClassHttpMethod(value.toString());
                    logger.info("[REQUEST_MAPPING] Class {} has HTTP method: {}",
                        context.getClassName(), value);
                }
                super.visit(name, value);
            }

            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name) || "path".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        @Override
                        public void visit(String name, Object value) {
                            if (context.getClassBasePath().isEmpty()) {
                                context.setClassBasePath(value.toString());
                                logger.info("[REQUEST_MAPPING] Class {} has base path (array): {}",
                                    context.getClassName(), value);
                            }
                            super.visit(name, value);
                        }
                    };
                } else if ("method".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        @Override
                        public void visit(String name, Object value) {
                            if (context.getClassHttpMethod().isEmpty()) {
                                context.setClassHttpMethod(value.toString());
                                logger.info("[REQUEST_MAPPING] Class {} has HTTP method (array): {}",
                                    context.getClassName(), value);
                            }
                            super.visit(name, value);
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    @Override
    public int getPriority() {
        return 80; // High priority for web mapping configuration
    }
}
