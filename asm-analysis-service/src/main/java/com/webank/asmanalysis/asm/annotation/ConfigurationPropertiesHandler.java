package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @ConfigurationProperties annotation.
 *
 * <p>Processes @ConfigurationProperties to extract configuration prefix.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ConfigurationPropertiesHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ConfigurationPropertiesHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.CONFIGURATION_PROPERTIES.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.debug("[CONFIG_PROPERTIES_HANDLER] @ConfigurationProperties detected on class {}",
            context.getClassName());
    }

    /**
     * Creates an AnnotationVisitor to process @ConfigurationProperties attributes.
     *
     * @param parentAv The parent annotation visitor
     * @param context The analysis context
     * @return AnnotationVisitor for processing configuration properties attributes
     */
    public AnnotationVisitor createAttributeVisitor(
        AnnotationVisitor parentAv,
        AnalysisContext context
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("prefix".equals(name) || "value".equals(name)) {
                    context.setConfigPropertiesPrefix(value.toString());
                    logger.info("[CONFIG_PROPERTIES] Class {} has @ConfigurationProperties with prefix: {}",
                        context.getClassName(), value);
                }
                super.visit(name, value);
            }
        };
    }

    @Override
    public int getPriority() {
        return 75; // High priority for configuration binding
    }
}
