package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Value annotation.
 *
 * <p>Handles Spring @Value annotation at field level.
 * Extracts configuration keys for property injection.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ValueAnnotationHandler implements FieldAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ValueAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.VALUE.equals(descriptor);
    }

    @Override
    public void handleField(FieldAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        logger.debug("[VALUE_FIELD_HANDLER] @Value detected on field {}.{}",
            context.getClassName(), context.getFieldName());
    }

    /**
     * Creates an AnnotationVisitor to process @Value attributes.
     *
     * @param parentAv The parent annotation visitor
     * @param context The analysis context
     * @param fieldName The field name
     * @return AnnotationVisitor for processing value attributes
     */
    public AnnotationVisitor createAttributeVisitor(
        AnnotationVisitor parentAv,
        AnalysisContext context,
        String fieldName
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    String configKey = extractConfigKey(value.toString());
                    if (configKey != null) {
                        logger.info("[VALUE_FIELD] Field {} has @Value: {}",
                            fieldName, configKey);
                    }
                }
                super.visit(name, value);
            }
        };
    }

    /**
     * Extracts configuration key from @Value expression.
     * Examples:
     * - "${app.name}" -> "app.name"
     * - "#{systemProperties['user.name']}" -> "systemProperties"
     *
     * @param value The @Value expression
     * @return The extracted configuration key
     */
    private String extractConfigKey(String value) {
        if (value == null) {
            return null;
        }

        // Handle ${...} placeholders
        if (value.startsWith("${") && value.endsWith("}")) {
            String inner = value.substring(2, value.length() - 1);
            // Extract key before colon (default value) or any other special character
            int colonIndex = inner.indexOf(':');
            if (colonIndex > 0) {
                return inner.substring(0, colonIndex).trim();
            }
            return inner.trim();
        }

        // Handle #{...} SpEL expressions
        if (value.startsWith("#{") && value.endsWith("}")) {
            return value.substring(2, value.length() - 1).trim();
        }

        return value;
    }

    @Override
    public int getPriority() {
        return 93; // High priority for configuration injection
    }
}
