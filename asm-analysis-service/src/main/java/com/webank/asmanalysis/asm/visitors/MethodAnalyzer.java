package com.webank.asmanalysis.asm.visitors;

import com.webank.asmanalysis.asm.AnalysisContext;
import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.annotation.AnnotationProcessor;
import com.webank.asmanalysis.asm.builder.MethodMetadata;
import org.objectweb.asm.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * Method visitor to extract method calls with line numbers.
 *
 * <p>Extracted from ClassAnalyzer inner class as part of refactoring to reduce complexity.
 * This class handles all method-level ASM visitation including:
 * <ul>
 *   <li>Method annotation processing (@Transactional, @Async, @Bean, @Scheduled, etc.)</li>
 *   <li>Method call edge creation</li>
 *   <li>Entry point detection</li>
 *   <li>API path mapping</li>
 * </ul>
 *
 * <p>Phase 2: Now uses MethodMetadata builder pattern for type-safe metadata access.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MethodAnalyzer extends MethodVisitor {
    private static final Logger logger = LoggerFactory.getLogger(MethodAnalyzer.class);

    // Feature flag for gradual migration to new annotation processor
    private static final boolean USE_NEW_ANNOTATION_PROCESSOR =
        Boolean.getBoolean("asm.new.annotation.processor");

    private final AnalysisContext context;
    private final AnnotationProcessor annotationProcessor;
    private final MethodMetadata metadata;  // Phase 2: Immutable metadata
    private final String currentMethodFqn;
    private final boolean isConstructor;
    private final List<String> constructorParamTypes;
    private final String methodName;
    private final String methodDescriptor;
    private int currentLine = -1;
    private int methodStartLine = -1;
    private Map<String, Object> methodNode;
    private String apiPath = "";
    private String httpMethod = "";
    private String injectionType = null;
    private String qualifierValue = null;
    private Map<Integer, String> parameterQualifiers = new HashMap<>();
    private boolean hasMyBatisAnnotation = false;
    private String mybatisOperationType = "";
    private String mybatisAnnotationDescriptor = "";

    // Transaction attributes
    private String transactionPropagation = null;
    private String transactionIsolation = null;
    private Integer transactionTimeout = null;
    private Boolean transactionReadOnly = null;
    private String transactionRollbackFor = null;
    private String transactionNoRollbackFor = null;

    // AOP attributes
    private String adviceType = null;
    private String pointcutExpression = null;
    private Integer order = null;

    // Async attributes
    private boolean isAsync = false;
    private String asyncExecutor = "";

    // @Bean method attributes
    private boolean isBeanMethod = false;
    private String beanName = "";
    private String initMethod = "";
    private String destroyMethod = "";
    private String autowireMode = "";
    private boolean beanPrimary = false;
    private String beanScope = "";
    private List<String> dependsOnBeans = new ArrayList<>();
    private String returnType = "";

    // Quartz scheduled task attributes
    private boolean isScheduled = false;
    private String scheduledCron = "";
    private String scheduledFixedDelay = "";
    private String scheduledFixedRate = "";

    /**
     * Creates a new MethodAnalyzer.
     *
     * @param context The shared analysis context for storing nodes and edges
     * @param annotationProcessor The annotation processor for handling annotations
     * @param currentMethodFqn The fully qualified name of the method
     * @param modifiers List of method modifiers (public, private, etc.)
     * @param isConstructor Whether this is a constructor
     * @param constructorParamTypes List of constructor parameter types
     * @param returnType The return type of the method
     * @param methodName The simple name of the method
     * @param methodDescriptor The JVM descriptor of the method
     */
    public MethodAnalyzer(
        AnalysisContext context,
        AnnotationProcessor annotationProcessor,
        String currentMethodFqn,
        List<String> modifiers,
        boolean isConstructor,
        List<String> constructorParamTypes,
        String returnType,
        String methodName,
        String methodDescriptor
    ) {
        super(Opcodes.ASM9);
        this.context = context;
        this.annotationProcessor = annotationProcessor;
        this.currentMethodFqn = currentMethodFqn;
        this.isConstructor = isConstructor;
        this.constructorParamTypes = constructorParamTypes != null ? constructorParamTypes : new ArrayList<>();
        this.returnType = returnType != null ? returnType : "";
        this.methodName = methodName;
        this.methodDescriptor = methodDescriptor;

        // Phase 2: Create MethodMetadata using builder pattern
        this.metadata = MethodMetadata.builder()
            .fqn(currentMethodFqn)
            .simpleName(methodName)
            .descriptor(methodDescriptor)
            .modifiers(modifiers)
            .parameterTypes(this.constructorParamTypes)
            .returnType(this.returnType)
            .isConstructor(isConstructor)
            .lineNumber(-1)
            .build();

        // Initialize method node
        methodNode = new HashMap<>();
        methodNode.put("fqn", currentMethodFqn);
        methodNode.put("nodeType", "method");
        methodNode.put("attributes", new HashMap<String, Object>());
        methodNode.put("lineNumber", -1);
        methodNode.put("modifiers", modifiers);
        methodNode.put("hasOverride", false);
        methodNode.put("isTransactional", false);
        methodNode.put("methodParamTypes", this.constructorParamTypes);
        methodNode.put("returnType", this.returnType);
        context.addNode(methodNode);

        // Create member edge
        Map<String, Object> memberEdge = new HashMap<>();
        memberEdge.put("edgeType", "member_of");
        memberEdge.put("fromFqn", currentMethodFqn);
        memberEdge.put("toFqn", context.getClassName());
        memberEdge.put("kind", "method");
        context.addEdge(memberEdge);
    }

    /**
     * Gets the immutable metadata for this method.
     * Phase 2: Provides type-safe access to method properties.
     *
     * @return The method metadata
     */
    public MethodMetadata getMetadata() {
        return metadata;
    }

    @Override
    public AnnotationVisitor visitAnnotation(String descriptor, boolean visible) {
        // Phase 1.3: Gradual migration to strategy pattern-based annotation handling
        // Use new AnnotationProcessor for method annotations when feature flag is enabled
        if (USE_NEW_ANNOTATION_PROCESSOR) {
            boolean hasHandler = annotationProcessor.hasHandlerFor(descriptor);

            if (hasHandler) {
                boolean handled = annotationProcessor.processMethodAnnotation(
                    descriptor, visible, methodNode, context);

                if (handled) {
                    // Set local state for annotations that need special attribute processing
                    if (AnnotationConstants.ASYNC.equals(descriptor)) {
                        this.isAsync = true;
                        return createAsyncAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.SPRING_TRANSACTIONAL.equals(descriptor) ||
                               AnnotationConstants.JAVAX_TRANSACTIONAL.equals(descriptor) ||
                               AnnotationConstants.JAKARTA_TRANSACTIONAL.equals(descriptor)) {
                        methodNode.put("isTransactional", true);
                        context.setNeedsProxy(true);
                        return createTransactionalAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.BEFORE.equals(descriptor) ||
                               AnnotationConstants.AFTER.equals(descriptor) ||
                               AnnotationConstants.AROUND.equals(descriptor) ||
                               AnnotationConstants.AFTER_RETURNING.equals(descriptor) ||
                               AnnotationConstants.AFTER_THROWING.equals(descriptor)) {
                        // Set local state for compatibility with existing code
                        if (AnnotationConstants.BEFORE.equals(descriptor)) adviceType = "@Before";
                        else if (AnnotationConstants.AFTER.equals(descriptor)) adviceType = "@After";
                        else if (AnnotationConstants.AROUND.equals(descriptor)) adviceType = "@Around";
                        else if (AnnotationConstants.AFTER_RETURNING.equals(descriptor)) adviceType = "@AfterReturning";
                        else if (AnnotationConstants.AFTER_THROWING.equals(descriptor)) adviceType = "@AfterThrowing";
                        return createAopAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.BEAN.equals(descriptor)) {
                        this.isBeanMethod = true;
                        context.setNeedsProxy(true);
                        return createBeanAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.SCHEDULED.equals(descriptor)) {
                        this.isScheduled = true;
                        return createScheduledAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (getHttpMethodType(descriptor) != null && !getHttpMethodType(descriptor).isEmpty()) {
                        this.httpMethod = getHttpMethodType(descriptor);
                        return createRequestMappingAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.ORDER.equals(descriptor)) {
                        return createOrderAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.DEPENDS_ON.equals(descriptor)) {
                        return createDependsOnAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.SCOPE.equals(descriptor)) {
                        return createScopeAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (AnnotationConstants.QUALIFIER.equals(descriptor)) {
                        return createQualifierAnnotationVisitor(super.visitAnnotation(descriptor, visible));
                    } else if (descriptor.startsWith("Lorg/apache/ibatis/annotations/")) {
                        return createMyBatisAnnotationVisitor(descriptor, super.visitAnnotation(descriptor, visible));
                    }

                    return super.visitAnnotation(descriptor, visible);
                }
            }
        }

        // Old code path (kept for backward compatibility and fallback)
        if (AnnotationConstants.OVERRIDE.equals(descriptor)) {
            methodNode.put("hasOverride", true);
        }

        if (AnnotationConstants.SPRING_TRANSACTIONAL.equals(descriptor) ||
            AnnotationConstants.JAVAX_TRANSACTIONAL.equals(descriptor) ||
            AnnotationConstants.JAKARTA_TRANSACTIONAL.equals(descriptor)) {
            methodNode.put("isTransactional", true);
            context.setNeedsProxy(true);

            return createTransactionalAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // AOP annotations
        boolean isAopAnnotation = false;
        if (AnnotationConstants.BEFORE.equals(descriptor)) { adviceType = "@Before"; isAopAnnotation = true; }
        else if (AnnotationConstants.AFTER.equals(descriptor)) { adviceType = "@After"; isAopAnnotation = true; }
        else if (AnnotationConstants.AROUND.equals(descriptor)) { adviceType = "@Around"; isAopAnnotation = true; }
        else if (AnnotationConstants.AFTER_RETURNING.equals(descriptor)) { adviceType = "@AfterReturning"; isAopAnnotation = true; }
        else if (AnnotationConstants.AFTER_THROWING.equals(descriptor)) { adviceType = "@AfterThrowing"; isAopAnnotation = true; }
        else if (AnnotationConstants.POINTCUT.equals(descriptor)) { adviceType = "@Pointcut"; isAopAnnotation = true; }
        else if (AnnotationConstants.ORDER.equals(descriptor)) {
            return createOrderAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        if (isAopAnnotation) {
            return createAopAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // Dependency injection annotations
        if (AnnotationConstants.AUTOWIRED.equals(descriptor)) injectionType = "autowired";
        else if (AnnotationConstants.INJECT.equals(descriptor)) injectionType = "inject";
        else if (AnnotationConstants.RESOURCE.equals(descriptor)) injectionType = "resource";
        else if (AnnotationConstants.QUALIFIER.equals(descriptor)) {
            return createQualifierAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // REST mapping annotations
        String type = getHttpMethodType(descriptor);
        if (!type.isEmpty()) {
            this.httpMethod = type;
            return createRequestMappingAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // MyBatis annotations
        if (descriptor.startsWith("Lorg/apache/ibatis/annotations/")) {
            return createMyBatisAnnotationVisitor(descriptor, super.visitAnnotation(descriptor, visible));
        }

        if (descriptor.startsWith(AnnotationConstants.MYBATIS_PLUS_PREFIX)) {
            hasMyBatisAnnotation = true;
            mybatisAnnotationDescriptor = descriptor;
            mybatisOperationType = "mybatis_plus";
        }

        // @Bean annotation
        if (AnnotationConstants.BEAN.equals(descriptor)) {
            this.isBeanMethod = true;
            context.setNeedsProxy(true);
            return createBeanAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // @Scope annotation
        if (AnnotationConstants.SCOPE.equals(descriptor)) {
            return createScopeAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        if (AnnotationConstants.PRIMARY.equals(descriptor)) beanPrimary = true;

        if (AnnotationConstants.DEPENDS_ON.equals(descriptor)) {
            return createDependsOnAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // @Async annotation
        if (AnnotationConstants.ASYNC.equals(descriptor)) {
            this.isAsync = true;
            context.setNeedsProxy(true);
            return createAsyncAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        // @Scheduled annotation
        if (AnnotationConstants.SCHEDULED.equals(descriptor)) {
            this.isScheduled = true;
            return createScheduledAnnotationVisitor(super.visitAnnotation(descriptor, visible));
        }

        return super.visitAnnotation(descriptor, visible);
    }

    @Override
    public AnnotationVisitor visitParameterAnnotation(int parameter, String descriptor, boolean visible) {
        if (AnnotationConstants.QUALIFIER.equals(descriptor)) {
            return new AnnotationVisitor(Opcodes.ASM9, super.visitParameterAnnotation(parameter, descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("value".equals(name)) {
                        String qualifier = (value instanceof Type) ? ((Type) value).getClassName() : value.toString();
                        parameterQualifiers.put(parameter, qualifier);
                    }
                    super.visit(name, value);
                }
            };
        }
        return super.visitParameterAnnotation(parameter, descriptor, visible);
    }

    @Override
    public void visitLineNumber(int line, Label start) {
        this.currentLine = line;
        if (this.methodStartLine == -1) {
            this.methodStartLine = line;
            methodNode.put("lineNumber", line);
        }
        super.visitLineNumber(line, start);
    }

    @Override
    public void visitMethodInsn(int opcode, String owner, String name,
                                 String descriptor, boolean isInterface) {
        String targetClass = owner.replace('/', '.');
        String targetMethod = targetClass + "." + name + descriptorToSignature(descriptor);

        String kind;
        switch (opcode) {
            case Opcodes.INVOKEVIRTUAL: kind = "invokevirtual"; break;
            case Opcodes.INVOKESTATIC: kind = "invokestatic"; break;
            case Opcodes.INVOKEINTERFACE: kind = "invokeinterface"; break;
            case Opcodes.INVOKESPECIAL: kind = name.equals("<init>") ? "new" : "invokespecial"; break;
            case Opcodes.INVOKEDYNAMIC: kind = "invokedynamic"; break;
            default: kind = "unknown";
        }

        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "call");
        edge.put("fromFqn", currentMethodFqn);
        edge.put("toFqn", targetMethod);
        edge.put("kind", kind);
        edge.put("lineNumber", currentLine);

        // Detect MyBatis Plus BaseMapper method calls
        detectMyBatisPlusBaseMapperCall(edge, targetClass, name);

        context.addEdge(edge);

        super.visitMethodInsn(opcode, owner, name, descriptor, isInterface);
    }

    /**
     * Detect and annotate MyBatis Plus BaseMapper method calls.
     *
     * MyBatis Plus BaseMapper provides CRUD methods (insert, updateById, deleteById, selectById, etc.)
     * that are inherited by custom Mapper interfaces. These methods don't have explicit SQL mappings,
     * making them invisible to standard MyBatis annotation scanning.
     *
     * Detection heuristics:
     * 1. Method name matches BaseMapper method patterns (insert, update*, delete*, select*)
     * 2. Owner class name ends with "Mapper" (convention)
     * 3. If both conditions match, mark as potential BaseMapper call
     *
     * @param edge The edge being created for this method call
     * @param targetClass The target class (mapper interface)
     * @param methodName The method being called
     */
    private void detectMyBatisPlusBaseMapperCall(Map<String, Object> edge, String targetClass, String methodName) {
        // Only consider classes that follow Mapper naming convention
        if (!targetClass.endsWith("Mapper")) {
            return;
        }

        // Detect BaseMapper CRUD methods
        String operationType = null;

        if ("insert".equals(methodName)) {
            operationType = "INSERT";
        } else if (methodName.startsWith("update")) {
            // updateById, updateBatchById, update
            operationType = "UPDATE";
        } else if (methodName.startsWith("delete")) {
            // deleteById, deleteBatchIds, delete
            operationType = "DELETE";
        } else if (methodName.startsWith("select")) {
            // selectById, selectBatchIds, selectOne, selectList, selectCount, etc.
            operationType = "SELECT";
        }

        if (operationType != null) {
            // Mark this edge as a potential BaseMapper call
            // Store in metadata map for consistent handling with other edge metadata
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("mybatis_plus_basemapper_call", 1);  // Use integer for SQLite JSON extraction
            metadata.put("mybatis_plus_operation_type", operationType);
            metadata.put("mybatis_plus_mapper_class", targetClass);
            metadata.put("mybatis_plus_method_name", methodName);
            edge.put("metadata", metadata);

            logger.debug("Detected MyBatis Plus BaseMapper call: {}.{} ({})",
                    targetClass, methodName, operationType);
        }
    }

    @Override
    public void visitInvokeDynamicInsn(String name, String descriptor, Handle bootstrapMethodHandle, Object... bootstrapMethodArguments) {
        String bsmOwner = bootstrapMethodHandle.getOwner();
        if ("java/lang/invoke/StringConcatFactory".equals(bsmOwner)) return;

        if (!"java/lang/invoke/LambdaMetafactory".equals(bsmOwner)) return;

        Map<String, Object> edge = new HashMap<>();
        edge.put("edgeType", "call");
        edge.put("fromFqn", currentMethodFqn);
        edge.put("toFqn", "invokedynamic:" + name + descriptor);
        edge.put("kind", "invokedynamic");
        edge.put("lineNumber", currentLine);
        edge.put("bootstrap_method_owner", bootstrapMethodHandle.getOwner().replace('/', '.'));
        edge.put("bootstrap_method_name", bootstrapMethodHandle.getName());
        context.addEdge(edge);

        handleLambdaMetafactory(name, descriptor, bootstrapMethodHandle, bootstrapMethodArguments);

        super.visitInvokeDynamicInsn(name, descriptor, bootstrapMethodHandle, bootstrapMethodArguments);
    }

    @Override
    public void visitEnd() {
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) methodNode.get("attributes");
        if (attributes == null) {
            attributes = new HashMap<>();
            methodNode.put("attributes", attributes);
        }

        // Process dependency injection edges
        processDependencyInjectionEdges();

        // Process API path
        processApiPath();

        // Process MyBatis annotations
        processMyBatisAnnotations(attributes);

        // Process transactional attributes
        processTransactionalAttributes(attributes);

        // Process AOP attributes
        processAopAttributes(attributes);

        // Process async attributes
        processAsyncAttributes(attributes);

        // Process bean method attributes
        processBeanMethodAttributes(attributes);

        // Process entry point detection
        processEntryPointDetection();

        // Process scheduled attributes
        processScheduledAttributes(attributes);

        super.visitEnd();
    }

    // ========== Private Helper Methods ==========

    private AnnotationVisitor createTransactionalAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                switch (name) {
                    case "propagation": transactionPropagation = value.toString(); break;
                    case "isolation": transactionIsolation = value.toString(); break;
                    case "timeout":
                        if (value instanceof Integer) transactionTimeout = (Integer) value;
                        else if (value instanceof String) {
                            try { transactionTimeout = Integer.parseInt((String) value); } catch (NumberFormatException ignored) {}
                        }
                        break;
                    case "readOnly":
                        if (value instanceof Boolean) transactionReadOnly = (Boolean) value;
                        else if (value instanceof String) transactionReadOnly = Boolean.parseBoolean((String) value);
                        break;
                    case "rollbackFor":
                    case "rollbackForClassName":
                        if (value instanceof Type) transactionRollbackFor = ((Type) value).getClassName();
                        else if (value instanceof String) transactionRollbackFor = (String) value;
                        else if (value instanceof String[]) transactionRollbackFor = String.join(",", (String[]) value);
                        break;
                    case "noRollbackFor":
                    case "noRollbackForClassName":
                        if (value instanceof Type) transactionNoRollbackFor = ((Type) value).getClassName();
                        else if (value instanceof String) transactionNoRollbackFor = (String) value;
                        else if (value instanceof String[]) transactionNoRollbackFor = String.join(",", (String[]) value);
                        break;
                }
                super.visit(name, value);
            }

            @Override
            public AnnotationVisitor visitArray(String name) {
                // Skip array processing for rollbackFor/noRollbackFor to avoid complexity
                return super.visitArray(name);
            }

            @Override
            public void visitEnum(String name, String descriptor, String value) {
                if ("propagation".equals(name)) transactionPropagation = value;
                else if ("isolation".equals(name)) transactionIsolation = value;
                super.visitEnum(name, descriptor, value);
            }
        };
    }

    private AnnotationVisitor createRollbackForArrayVisitor(String name, AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            private List<String> values = new ArrayList<>();
            @Override
            public void visit(String name, Object value) {
                if (value instanceof Type) values.add(((Type) value).getClassName());
                else if (value instanceof String) values.add((String) value);
                super.visit(name, value);
            }
            @Override
            public void visitEnd() {
                if (!values.isEmpty()) {
                    String joined = String.join(",", values);
                    if (name.startsWith("rollbackFor")) transactionRollbackFor = joined;
                    else if (name.startsWith("noRollbackFor")) transactionNoRollbackFor = joined;
                }
                super.visitEnd();
            }
        };
    }

    private AnnotationVisitor createOrderAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    try { order = Integer.parseInt(value.toString()); } catch (Exception ignored) {}
                }
                super.visit(name, value);
            }
        };
    }

    private AnnotationVisitor createAopAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name) || "pointcut".equals(name)) pointcutExpression = value.toString();
                super.visit(name, value);
            }
            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        private List<String> expressions = new ArrayList<>();
                        @Override
                        public void visit(String name, Object value) {
                            if (value instanceof String) expressions.add((String) value);
                            super.visit(name, value);
                        }
                        @Override
                        public void visitEnd() {
                            if (!expressions.isEmpty()) pointcutExpression = String.join(",", expressions);
                            super.visitEnd();
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    private AnnotationVisitor createQualifierAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) qualifierValue = value.toString();
                super.visit(name, value);
            }
        };
    }

    private AnnotationVisitor createRequestMappingAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name) || "path".equals(name)) apiPath = value.toString();
                super.visit(name, value);
            }
            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name) || "path".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        @Override
                        public void visit(String name, Object value) {
                            if (apiPath.isEmpty()) apiPath = value.toString();
                            super.visit(name, value);
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    private AnnotationVisitor createMyBatisAnnotationVisitor(String descriptor, AnnotationVisitor av) {
        hasMyBatisAnnotation = true;
        mybatisAnnotationDescriptor = descriptor;
        if (descriptor.contains("Select")) mybatisOperationType = "select";
        else if (descriptor.contains("Insert")) mybatisOperationType = "insert";
        else if (descriptor.contains("Update")) mybatisOperationType = "update";
        else if (descriptor.contains("Delete")) mybatisOperationType = "delete";
        else if (descriptor.contains("Provider")) mybatisOperationType = "provider";
        else if (descriptor.contains("Result")) mybatisOperationType = "results";
        else mybatisOperationType = "other";

        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) methodNode.put("mybatisSqlValue", value.toString());
                super.visit(name, value);
            }
            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        private List<String> sqlStatements = new ArrayList<>();
                        @Override
                        public void visit(String name, Object value) {
                            sqlStatements.add(value.toString());
                            super.visit(name, value);
                        }
                        @Override
                        public void visitEnd() {
                            if (!sqlStatements.isEmpty()) methodNode.put("mybatisSqlStatements", sqlStatements);
                            super.visitEnd();
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    private AnnotationVisitor createBeanAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                switch (name) {
                    case "value":
                    case "name":
                        if (value instanceof String[]) {
                            String[] names = (String[]) value;
                            if (names.length > 0) beanName = names[0];
                        } else if (value instanceof String) beanName = (String) value;
                        break;
                    case "initMethod": initMethod = value.toString(); break;
                    case "destroyMethod": destroyMethod = value.toString(); break;
                    case "autowire": autowireMode = value.toString(); break;
                }
                super.visit(name, value);
            }
            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name) || "name".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        private List<String> names = new ArrayList<>();
                        @Override
                        public void visit(String name, Object value) {
                            if (value instanceof String) names.add((String) value);
                            super.visit(name, value);
                        }
                        @Override
                        public void visitEnd() {
                            if (!names.isEmpty()) beanName = names.get(0);
                            super.visitEnd();
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    private AnnotationVisitor createScopeAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) beanScope = value.toString();
                super.visit(name, value);
            }
        };
    }

    private AnnotationVisitor createDependsOnAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    if (value instanceof String) dependsOnBeans.add((String) value);
                    else if (value instanceof String[]) dependsOnBeans.addAll(Arrays.asList((String[]) value));
                }
                super.visit(name, value);
            }
            @Override
            public AnnotationVisitor visitArray(String name) {
                if ("value".equals(name)) {
                    return new AnnotationVisitor(Opcodes.ASM9, super.visitArray(name)) {
                        private List<String> beans = new ArrayList<>();
                        @Override
                        public void visit(String name, Object value) {
                            if (value instanceof String) beans.add((String) value);
                            super.visit(name, value);
                        }
                        @Override
                        public void visitEnd() {
                            if (!beans.isEmpty()) dependsOnBeans = beans;
                            super.visitEnd();
                        }
                    };
                }
                return super.visitArray(name);
            }
        };
    }

    private AnnotationVisitor createAsyncAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) asyncExecutor = value.toString();
                super.visit(name, value);
            }
        };
    }

    private AnnotationVisitor createScheduledAnnotationVisitor(AnnotationVisitor av) {
        return new AnnotationVisitor(Opcodes.ASM9, av) {
            @Override
            public void visit(String name, Object value) {
                if ("cron".equals(name) || "cronExpression".equals(name)) scheduledCron = value.toString();
                else if ("fixedDelay".equals(name) || "fixedDelayString".equals(name)) scheduledFixedDelay = value.toString();
                else if ("fixedRate".equals(name) || "fixedRateString".equals(name)) scheduledFixedRate = value.toString();
                super.visit(name, value);
            }
        };
    }

    private String getHttpMethodType(String descriptor) {
        if (AnnotationConstants.GET_MAPPING.equals(descriptor)) return "GET";
        else if (AnnotationConstants.POST_MAPPING.equals(descriptor)) return "POST";
        else if (AnnotationConstants.PUT_MAPPING.equals(descriptor)) return "PUT";
        else if (AnnotationConstants.DELETE_MAPPING.equals(descriptor)) return "DELETE";
        else if (AnnotationConstants.PATCH_MAPPING.equals(descriptor)) return "PATCH";
        else if (AnnotationConstants.REQUEST_MAPPING.equals(descriptor)) return "ALL";
        return "";
    }

    private void handleLambdaMetafactory(String name, String descriptor, Handle bootstrapMethodHandle, Object... bootstrapMethodArguments) {
        try {
            if (bootstrapMethodHandle.getName().equals("metafactory") ||
                bootstrapMethodHandle.getName().equals("altMetafactory")) {
                if (bootstrapMethodArguments.length >= 3) {
                    Object implMethod = bootstrapMethodArguments[1];
                    if (implMethod instanceof Handle) {
                        Handle implHandle = (Handle) implMethod;
                        String implClass = implHandle.getOwner().replace('/', '.');
                        String implMethodName = implHandle.getName();
                        String implDesc = implHandle.getDesc();
                        String targetFqn = implClass + "." + implMethodName + descriptorToSignature(implDesc);

                        Map<String, Object> lambdaEdge = new HashMap<>();
                        lambdaEdge.put("edgeType", "call");
                        lambdaEdge.put("fromFqn", currentMethodFqn);
                        lambdaEdge.put("toFqn", targetFqn);
                        lambdaEdge.put("kind", "lambda");
                        lambdaEdge.put("lineNumber", currentLine);
                        lambdaEdge.put("lambda_name", name);
                        lambdaEdge.put("lambda_descriptor", descriptor);
                        lambdaEdge.put("bootstrap_method_owner", bootstrapMethodHandle.getOwner().replace('/', '.'));
                        lambdaEdge.put("bootstrap_method_name", bootstrapMethodHandle.getName());
                        context.addEdge(lambdaEdge);
                    }
                }
            } else {
                String targetClass = bootstrapMethodHandle.getOwner().replace('/', '.');
                String targetMethod = bootstrapMethodHandle.getName();
                String targetDesc = bootstrapMethodHandle.getDesc();
                String targetFqn = targetClass + "." + targetMethod + descriptorToSignature(targetDesc);

                Map<String, Object> methodRefEdge = new HashMap<>();
                methodRefEdge.put("edgeType", "call");
                methodRefEdge.put("fromFqn", currentMethodFqn);
                methodRefEdge.put("toFqn", targetFqn);
                methodRefEdge.put("kind", "method_reference");
                methodRefEdge.put("lineNumber", currentLine);
                methodRefEdge.put("bootstrap_method_owner", bootstrapMethodHandle.getOwner().replace('/', '.'));
                methodRefEdge.put("bootstrap_method_name", bootstrapMethodHandle.getName());
                context.addEdge(methodRefEdge);
            }
        } catch (Exception e) {
            logger.warn("[INVOKEDYNAMIC] Failed to parse lambda/method reference: {}", e.getMessage());
        }
    }

    private void processDependencyInjectionEdges() {
        String kind = isConstructor ? "constructor:" : "setter:";
        if (injectionType != null && !constructorParamTypes.isEmpty()) {
            for (int i = 0; i < constructorParamTypes.size(); i++) {
                String paramType = constructorParamTypes.get(i);
                Map<String, Object> edge = new HashMap<>();
                edge.put("edgeType", "member_of");
                edge.put("fromFqn", paramType);
                edge.put("toFqn", context.getClassName());
                edge.put("kind", kind + injectionType);
                String qualifier = parameterQualifiers.get(i);
                if (qualifier == null) qualifier = qualifierValue;
                edge.put("qualifier", qualifier);
                context.addEdge(edge);
            }
        }
    }

    private void processApiPath() {
        if (!apiPath.isEmpty()) {
            String fullPath = apiPath;
            String finalHttpMethod = this.httpMethod;
            String classBasePath = context.getClassBasePath();
            String classHttpMethod = context.getClassHttpMethod();

            if (!classBasePath.isEmpty()) {
                String base = classBasePath.startsWith("/") ? classBasePath : "/" + classBasePath;
                String methodPath = apiPath.startsWith("/") ? apiPath : "/" + apiPath;
                base = base.replaceAll("/+", "/");
                methodPath = methodPath.replaceAll("/+", "/");

                if (base.endsWith("/") && methodPath.startsWith("/")) {
                    fullPath = base + methodPath.substring(1);
                } else if (!base.endsWith("/") && !methodPath.startsWith("/")) {
                    fullPath = base + "/" + methodPath;
                } else {
                    fullPath = base + methodPath;
                }
                fullPath = fullPath.replaceAll("/+", "/");
            }

            if (finalHttpMethod.isEmpty() || "ALL".equals(finalHttpMethod)) {
                if (!classHttpMethod.isEmpty()) finalHttpMethod = classHttpMethod;
            }

            methodNode.put("apiPath", fullPath);
            methodNode.put("httpMethod", finalHttpMethod);
        }
    }

    private void processMyBatisAnnotations(Map<String, Object> attributes) {
        if (hasMyBatisAnnotation) {
            methodNode.put("hasMyBatisAnnotation", true);
            methodNode.put("mybatisOperationType", mybatisOperationType);
            methodNode.put("mybatisAnnotationDescriptor", mybatisAnnotationDescriptor);
        }
    }

    private void processTransactionalAttributes(Map<String, Object> attributes) {
        if (methodNode.containsKey("isTransactional") && (Boolean) methodNode.get("isTransactional")) {
            Map<String, Object> transactionAttributes = new HashMap<>();
            if (transactionPropagation != null) transactionAttributes.put("propagation", transactionPropagation);
            if (transactionIsolation != null) transactionAttributes.put("isolation", transactionIsolation);
            if (transactionTimeout != null) transactionAttributes.put("timeout", transactionTimeout);
            if (transactionReadOnly != null) transactionAttributes.put("readOnly", transactionReadOnly);
            if (transactionRollbackFor != null) transactionAttributes.put("rollbackFor", transactionRollbackFor);
            if (transactionNoRollbackFor != null) transactionAttributes.put("noRollbackFor", transactionNoRollbackFor);

            if (!transactionAttributes.isEmpty()) {
                methodNode.put("transactionAttributes", transactionAttributes);
                attributes.put("transactional", true);
                if (transactionPropagation != null) attributes.put("transaction_propagation", transactionPropagation);
                if (transactionIsolation != null) attributes.put("transaction_isolation", transactionIsolation);
                if (transactionTimeout != null) attributes.put("transaction_timeout", transactionTimeout);
                if (transactionReadOnly != null) attributes.put("transaction_read_only", transactionReadOnly);
                if (transactionRollbackFor != null) attributes.put("transaction_rollback_for", transactionRollbackFor);
                if (transactionNoRollbackFor != null) attributes.put("transaction_no_rollback_for", transactionNoRollbackFor);
            }
        }
    }

    private void processAopAttributes(Map<String, Object> attributes) {
        if (adviceType != null) {
            Map<String, Object> aopAttributes = new HashMap<>();
            aopAttributes.put("adviceType", adviceType);
            if (pointcutExpression != null) aopAttributes.put("pointcutExpression", pointcutExpression);
            if (order != null) aopAttributes.put("order", order);

            methodNode.put("aopAttributes", aopAttributes);
            attributes.put("advised", true);
            attributes.put("advice_type", adviceType);
            if (pointcutExpression != null) attributes.put("pointcut_expression", pointcutExpression);
            if (order != null) attributes.put("advice_order", order);
        }
    }

    private void processAsyncAttributes(Map<String, Object> attributes) {
        if (isAsync) {
            methodNode.put("isAsync", true);
            Map<String, Object> asyncAttributes = new HashMap<>();
            asyncAttributes.put("isAsync", true);
            if (!asyncExecutor.isEmpty()) {
                asyncAttributes.put("executor", asyncExecutor);
                asyncAttributes.put("value", asyncExecutor);
            }
            methodNode.put("asyncAttributes", asyncAttributes);
            attributes.put("async", true);
            if (!asyncExecutor.isEmpty()) attributes.put("async_executor", asyncExecutor);
        }
    }

    private void processBeanMethodAttributes(Map<String, Object> attributes) {
        if (isBeanMethod) {
            methodNode.put("isBeanMethod", true);
            Map<String, Object> beanAttributes = new HashMap<>();
            beanAttributes.put("isBeanMethod", true);
            if (!beanName.isEmpty()) beanAttributes.put("beanName", beanName);
            if (qualifierValue != null) beanAttributes.put("qualifier", qualifierValue);
            if (!parameterQualifiers.isEmpty()) beanAttributes.put("parameterQualifiers", new HashMap<>(parameterQualifiers));
            if (!initMethod.isEmpty()) beanAttributes.put("initMethod", initMethod);
            if (!destroyMethod.isEmpty()) beanAttributes.put("destroyMethod", destroyMethod);
            if (!autowireMode.isEmpty()) beanAttributes.put("autowireMode", autowireMode);
            if (beanPrimary) beanAttributes.put("primary", true);
            if (!beanScope.isEmpty()) beanAttributes.put("scope", beanScope);
            if (!dependsOnBeans.isEmpty()) beanAttributes.put("dependsOn", dependsOnBeans);
            if (!returnType.isEmpty()) beanAttributes.put("returnType", returnType);

            methodNode.put("beanAttributes", beanAttributes);
            attributes.put("bean_method", true);
            if (!beanName.isEmpty()) attributes.put("bean_name", beanName);
            if (qualifierValue != null) attributes.put("bean_qualifier", qualifierValue);
            if (!initMethod.isEmpty()) attributes.put("bean_init_method", initMethod);
            if (!destroyMethod.isEmpty()) attributes.put("bean_destroy_method", destroyMethod);
            if (beanPrimary) attributes.put("bean_primary", true);
            if (!beanScope.isEmpty()) attributes.put("bean_scope", beanScope);
            if (!dependsOnBeans.isEmpty()) attributes.put("bean_depends_on", dependsOnBeans);

            // Create bean dependency edges
            for (int i = 0; i < constructorParamTypes.size(); i++) {
                String paramType = constructorParamTypes.get(i);
                Map<String, Object> edge = new HashMap<>();
                edge.put("edgeType", "member_of");
                edge.put("fromFqn", paramType);
                edge.put("toFqn", context.getClassName());
                edge.put("kind", "bean_dependency");
                String qualifier = parameterQualifiers.get(i);
                edge.put("qualifier", qualifier);
                context.addEdge(edge);
            }
        }
    }

    private void processEntryPointDetection() {
        if (context.isQuartzJob() && "execute".equals(methodName) && "(Lorg/quartz/JobExecutionContext;)V".equals(methodDescriptor)) {
            methodNode.put("isEntryPoint", true);
            methodNode.put("entryPointType", "quartz_job");
            logger.info("[ENTRY_POINT] Quartz Job execute() method found: {}", currentMethodFqn);
        }

        if (context.isExtendsQuartzJobBean() && "executeInternal".equals(methodName) && "(Lorg/quartz/JobExecutionContext;)V".equals(methodDescriptor)) {
            methodNode.put("isEntryPoint", true);
            methodNode.put("entryPointType", "quartz_job_spring");
            logger.info("[ENTRY_POINT] Spring QuartzJobBean executeInternal() method found: {}", currentMethodFqn);
        }
    }

    private void processScheduledAttributes(Map<String, Object> attributes) {
        if (isScheduled) {
            methodNode.put("isEntryPoint", true);
            methodNode.put("entryPointType", "spring_scheduled");

            Map<String, Object> scheduleInfo = new HashMap<>();
            if (!scheduledCron.isEmpty()) scheduleInfo.put("cron", scheduledCron);
            if (!scheduledFixedDelay.isEmpty()) scheduleInfo.put("fixedDelay", scheduledFixedDelay);
            if (!scheduledFixedRate.isEmpty()) scheduleInfo.put("fixedRate", scheduledFixedRate);

            if (!scheduleInfo.isEmpty()) methodNode.put("scheduleInfo", scheduleInfo);

            attributes.put("scheduled", true);
            if (!scheduledCron.isEmpty()) attributes.put("scheduled_cron", scheduledCron);
            if (!scheduledFixedDelay.isEmpty()) attributes.put("scheduled_fixed_delay", scheduledFixedDelay);
            if (!scheduledFixedRate.isEmpty()) attributes.put("scheduled_fixed_rate", scheduledFixedRate);
        }
    }

    private String descriptorToSignature(String descriptor) {
        Type methodType = Type.getMethodType(descriptor);
        StringBuilder sig = new StringBuilder("(");

        Type[] args = methodType.getArgumentTypes();
        for (int i = 0; i < args.length; i++) {
            if (i > 0) sig.append(", ");
            sig.append(args[i].getClassName());
        }
        sig.append(")");

        return sig.toString();
    }
}
