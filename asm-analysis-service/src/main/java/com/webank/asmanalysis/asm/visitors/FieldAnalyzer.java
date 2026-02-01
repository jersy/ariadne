package com.webank.asmanalysis.asm.visitors;

import com.webank.asmanalysis.asm.AnalysisContext;
import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.annotation.AnnotationProcessor;
import com.webank.asmanalysis.asm.builder.EdgeBuilder;
import com.webank.asmanalysis.asm.builder.FieldMetadata;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.FieldVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.Type;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Field visitor to extract field dependency information.
 *
 * <p>Extracted from ClassAnalyzer inner class as part of refactoring to reduce complexity.
 * This class handles all field-level ASM visitation including:
 * <ul>
 *   <li>Dependency injection annotation processing (@Autowired, @Inject, @Resource)</li>
 *   <li>@Qualifier annotation processing</li>
 *   <li>@Value annotation processing for configuration keys</li>
 *   <li>Field type dependency edge creation</li>
 * </ul>
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class FieldAnalyzer extends FieldVisitor {
    private static final Logger logger = LoggerFactory.getLogger(FieldAnalyzer.class);

    // Feature flag for gradual migration to new annotation processor
    private static final boolean USE_NEW_ANNOTATION_PROCESSOR =
        Boolean.getBoolean("asm.new.annotation.processor");

    private final AnalysisContext context;
    private final AnnotationProcessor annotationProcessor;
    private final String className;
    private final String fieldName;
    private final String fieldDescriptor;
    private String injectionType = null;
    private String qualifierValue = null;

    // Phase 2: Immutable metadata
    private final FieldMetadata metadata;

    // Phase 2: Edge builder for creating edges
    private final EdgeBuilder edgeBuilder;

    /**
     * Creates a new FieldAnalyzer.
     *
     * @param context The shared analysis context for storing nodes and edges
     * @param annotationProcessor The annotation processor for handling annotations
     * @param className The name of the class containing the field
     * @param fieldName The name of the field
     * @param fieldDescriptor The JVM descriptor of the field
     * @param parentFv The parent FieldVisitor to delegate to
     */
    public FieldAnalyzer(
        AnalysisContext context,
        AnnotationProcessor annotationProcessor,
        String className,
        String fieldName,
        String fieldDescriptor,
        FieldVisitor parentFv
    ) {
        super(Opcodes.ASM9, parentFv);
        this.context = context;
        this.annotationProcessor = annotationProcessor;
        this.className = className;
        this.fieldName = fieldName;
        this.fieldDescriptor = fieldDescriptor;
        this.edgeBuilder = new EdgeBuilder(context);

        // Phase 2: Create FieldMetadata using builder pattern
        String fieldType = descriptorToClassName(fieldDescriptor);
        this.metadata = FieldMetadata.builder()
            .fieldName(fieldName)
            .className(className)
            .fieldType(fieldType != null ? fieldType : "")
            .descriptor(fieldDescriptor)
            .modifiers(new ArrayList<>())
            .build();
    }

    @Override
    public AnnotationVisitor visitAnnotation(String descriptor, boolean visible) {
        // Phase 1.3: Gradual migration to strategy pattern-based annotation handling
        // Use new AnnotationProcessor for field annotations when feature flag is enabled
        if (USE_NEW_ANNOTATION_PROCESSOR) {
            boolean hasHandler = annotationProcessor.hasHandlerFor(descriptor);

            if (hasHandler) {
                boolean handled = annotationProcessor.processFieldAnnotation(
                    descriptor, visible, className, fieldName, context);

                if (handled) {
                    // Set injection type for edge creation
                    if (AnnotationConstants.AUTOWIRED.equals(descriptor)) {
                        injectionType = "autowired";
                    } else if (AnnotationConstants.INJECT.equals(descriptor)) {
                        injectionType = "inject";
                    } else if (AnnotationConstants.RESOURCE.equals(descriptor)) {
                        injectionType = "resource";
                    }

                    // @Value and @Qualifier need special attribute processing
                    if (AnnotationConstants.VALUE.equals(descriptor)) {
                        return createValueAnnotationVisitor(descriptor, super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.QUALIFIER.equals(descriptor)) {
                        return createQualifierAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    }

                    return super.visitAnnotation(descriptor, visible);
                }
            }
        }

        // Old code path (kept for backward compatibility and fallback)
        if (AnnotationConstants.AUTOWIRED.equals(descriptor)) {
            injectionType = "autowired";
        } else if (AnnotationConstants.INJECT.equals(descriptor)) {
            injectionType = "inject";
        } else if (AnnotationConstants.RESOURCE.equals(descriptor)) {
            injectionType = "resource";
        } else if (AnnotationConstants.QUALIFIER.equals(descriptor)) {
            return createQualifierAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        } else if (AnnotationConstants.VALUE.equals(descriptor)) {
            return createValueAnnotationVisitor(descriptor, super.visitAnnotation(descriptor, visible));
        }
        return super.visitAnnotation(descriptor, visible);
    }

    @Override
    public void visitEnd() {
        String fieldType = descriptorToClassName(fieldDescriptor);
        if (fieldType != null && !isPrimitive(fieldType)) {
            // Phase 2: Use EdgeBuilder to create field dependency edge
            edgeBuilder.createFieldDependencyEdge(fieldType, className, injectionType, qualifierValue);
        }
        super.visitEnd();
    }

    /**
     * Gets the immutable metadata for this field.
     * Phase 2: Provides type-safe access to field properties.
     *
     * @return The field metadata
     */
    public FieldMetadata getMetadata() {
        return metadata;
    }

    // ========== Private Helper Methods ==========

    /**
     * Creates an AnnotationVisitor for @Qualifier annotation.
     */
    private AnnotationVisitor createQualifierAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    if (value instanceof Type) {
                        qualifierValue = ((Type) value).getClassName();
                    } else {
                        qualifierValue = value.toString();
                    }
                }
                super.visit(name, value);
            }
        };
    }

    /**
     * Creates an AnnotationVisitor for @Value annotation.
     */
    private AnnotationVisitor createValueAnnotationVisitor(String descriptor, AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String attrName, Object value) {
                if ("value".equals(attrName)) {
                    String configKey = extractConfigKey(value.toString());
                    if (configKey != null) {
                        Map<String, Object> usage = new HashMap<>();
                        usage.put("configKey", configKey);
                        usage.put("targetType", "field");
                        usage.put("targetFqn", className + "." + fieldName);
                        usage.put("usageType", "@Value");
                        usage.put("lineNumber", -1);
                        context.addConfigUsage(usage);
                        logger.info("[CONFIG_VALUE] Field {} in class {} has @Value: {}",
                            fieldName, className, configKey);
                    }
                }
                super.visit(attrName, value);
            }
        };
    }

    /**
     * Converts a JVM descriptor to a class name.
     * Example: "Ljava/lang/String;" -> "java.lang.String"
     *          "I" -> null (primitive)
     */
    private String descriptorToClassName(String descriptor) {
        if (descriptor == null) {
            return null;
        }

        // Array types
        if (descriptor.startsWith("[")) {
            return Type.getType(descriptor).getClassName();
        }

        // Object types
        if (descriptor.startsWith("L") && descriptor.endsWith(";")) {
            return descriptor.substring(1, descriptor.length() - 1).replace('/', '.');
        }

        // Primitive types - return null as we don't create edges for primitives
        return null;
    }

    /**
     * Checks if a type name represents a primitive type.
     */
    private boolean isPrimitive(String typeName) {
        if (typeName == null) {
            return true;
        }

        // Check for common primitive types and their wrapper classes
        return typeName.equals("byte") || typeName.equals("short") ||
               typeName.equals("int") || typeName.equals("long") ||
               typeName.equals("float") || typeName.equals("double") ||
               typeName.equals("boolean") || typeName.equals("char") ||
               typeName.equals("java.lang.Byte") || typeName.equals("java.lang.Short") ||
               typeName.equals("java.lang.Integer") || typeName.equals("java.lang.Long") ||
               typeName.equals("java.lang.Float") || typeName.equals("java.lang.Double") ||
               typeName.equals("java.lang.Boolean") || typeName.equals("java.lang.Character") ||
               typeName.equals("java.lang.String");
    }

    /**
     * Extracts configuration key from @Value annotation value.
     * Examples:
     *   "${app.name}" -> "app.name"
     *   "#{configBean.property}" -> null (SpEL expression, not a simple key)
     *   "literal value" -> null (not a config reference)
     */
    private String extractConfigKey(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }

        // Check for property placeholder syntax: ${key}
        if (value.startsWith("${") && value.endsWith("}")) {
            String key = value.substring(2, value.length() - 1);
            // Handle default values: ${key:defaultValue}
            int colonIndex = key.indexOf(':');
            if (colonIndex > 0) {
                return key.substring(0, colonIndex);
            }
            return key;
        }

        // SpEL expressions start with #{
        if (value.startsWith("#{")) {
            return null;
        }

        // Literal values don't represent config keys
        return null;
    }
}
