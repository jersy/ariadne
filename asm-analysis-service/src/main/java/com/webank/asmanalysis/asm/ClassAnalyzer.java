package com.webank.asmanalysis.asm;

import com.webank.asmanalysis.asm.annotation.AnnotationProcessor;
import com.webank.asmanalysis.asm.builder.ClassMetadata;
import com.webank.asmanalysis.asm.builder.EdgeBuilder;
import com.webank.asmanalysis.asm.visitors.FieldAnalyzer;
import com.webank.asmanalysis.asm.visitors.MethodAnalyzer;
import org.objectweb.asm.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Analyzes a single .class file using ASM.
 * Refactored to use AnalysisContext for state management.
 */
public class ClassAnalyzer extends ClassVisitor {
    private static final Logger logger = LoggerFactory.getLogger(ClassAnalyzer.class);

    // Feature flag for gradual migration to new annotation processor
    // Enable with: -Dasm.new.annotation.processor=true
    private static final boolean USE_NEW_ANNOTATION_PROCESSOR =
        Boolean.getBoolean("asm.new.annotation.processor");

    // State is now delegated to the context
    private final AnalysisContext context;

    // Annotation processor for strategy pattern-based annotation handling
    private final AnnotationProcessor annotationProcessor;

    // Phase 2: Immutable metadata
    private ClassMetadata metadata;

    // Phase 2: Edge builder for creating edges
    private final EdgeBuilder edgeBuilder;

    public ClassAnalyzer(Path classFile) {
        super(Opcodes.ASM9);
        this.context = new AnalysisContext(classFile);
        this.annotationProcessor = new AnnotationProcessor(context);
        this.edgeBuilder = new EdgeBuilder(context);
    }

    // Getters for result retrieval (delegated to context)
    public List<Map<String, Object>> getNodes() {
        return context.getNodes();
    }

    public List<Map<String, Object>> getEdges() {
        return context.getEdges();
    }

    /**
     * Gets the immutable metadata for this class.
     * Phase 2: Provides type-safe access to class properties.
     *
     * @return The class metadata, or null if not yet initialized
     */
    public ClassMetadata getMetadata() {
        return metadata;
    }

    public void analyze() throws IOException {
        byte[] classBytes = Files.readAllBytes(context.getClassFile());
        ClassReader reader = new ClassReader(classBytes);
        reader.accept(this, ClassReader.EXPAND_FRAMES);
    }

    @Override
    public void visit(int version, int access, String name, String signature,
                      String superName, String[] interfaces) {
        // Convert internal name to FQN: com/example/MyClass -> com.example.MyClass
        String className = name.replace('/', '.');
        context.setClassName(className);
        logger.info("[CLASS_VISIT] Visiting class: {} (internal name: {})", className, name);

        context.setInterface((access & Opcodes.ACC_INTERFACE) != 0);
        context.setEnum((access & Opcodes.ACC_ENUM) != 0);
        context.setAbstract((access & Opcodes.ACC_ABSTRACT) != 0);
        context.setModifiers(parseModifiers(access));

        // Async/proxy detection: check if class is final and has interfaces
        context.setFinalClass((access & Opcodes.ACC_FINAL) != 0);
        context.setHasInterfaces(interfaces != null && interfaces.length > 0);

        // Heuristic detection: Interface with name ending with "Mapper" is likely MyBatis Mapper
        if (context.isInterface() && className.endsWith("Mapper")) {
            context.setMyBatisMapper(true);
            if (context.getMybatisDetectionMethod().isEmpty()) {
                context.setMybatisDetectionMethod("name_pattern");
            }
            context.setMybatisMapperType("interface");
            context.setMybatisMappingSource("annotation"); // Assume annotation-based mapping for interface
        }

        // Detect if this class is an entity (extends AuditableModel or similar)
        boolean isEntity = false;
        if (superName != null) {
            String superFqn = superName.replace('/', '.');
            // Check if extends AuditableModel (direct or via package convention)
            isEntity = superFqn.contains("AuditableModel") ||
                       (className.contains(".db.") && !className.equals("com.webank.db.BaseModel"));  // Configurable

            // Check if class extends Spring's QuartzJobBean (Phase 2.6 enhancement)
            if ("org.springframework.scheduling.quartz.QuartzJobBean".equals(superFqn)) {
                context.setExtendsQuartzJobBean(true);
                logger.info("[QUARTZ_JOB_BEAN] Class extends Spring QuartzJobBean: {}", className);
            }
        }

        // Create class node
        Map<String, Object> classNode = new HashMap<>();
        classNode.put("fqn", className);
        classNode.put("attributes", new HashMap<String, Object>());
        classNode.put("nodeType", context.isInterface() ? "interface" : (context.isEnum() ? "enum" : "class"));
        classNode.put("modifiers", context.getModifiers());
        classNode.put("isInterface", context.isInterface());
        classNode.put("isEnum", context.isEnum());
        classNode.put("isAbstract", context.isAbstract());
        classNode.put("isEntity", isEntity);
        classNode.put("isMyBatisMapper", context.isMyBatisMapper());
        if (context.isMyBatisMapper()) {
            if (!context.getMybatisMapperType().isEmpty()) {
                classNode.put("mybatisMapperType", context.getMybatisMapperType());
            }
            if (!context.getMybatisMappingSource().isEmpty()) {
                classNode.put("mybatisMappingSource", context.getMybatisMappingSource());
            }
        }

        // Note: Spring bean info, config properties, AOP, etc. are added in updateClassNode()
        // Here we just set the initial structure.
        context.setClassNode(classNode);
        context.addNode(classNode);

        // Phase 2: Create ClassMetadata using builder pattern
        List<String> interfaceList = interfaces != null ?
            Arrays.stream(interfaces).map(i -> i.replace('/', '.')).toList() : Collections.emptyList();
        String superFqn = superName != null ? superName.replace('/', '.') : "java.lang.Object";

        this.metadata = ClassMetadata.builder()
            .className(className)
            .superClassName(superFqn)
            .interfaces(interfaceList)
            .modifiers(context.getModifiers())
            .isInterface(context.isInterface())
            .isEnum(context.isEnum())
            .isAbstract(context.isAbstract())
            .version(version)
            .build();

        // Inheritance edges - using EdgeBuilder
        if (superName != null && !superName.equals("java/lang/Object")) {
            edgeBuilder.createInheritanceEdge(className, superFqn);
        }

        // Interface implementations - using EdgeBuilder
        if (interfaces != null) {
            for (String iface : interfaces) {
                String ifaceFqn = iface.replace('/', '.');
                edgeBuilder.createImplementationEdge(className, ifaceFqn);

                // Check if this interface extends a MyBatis base interface
                if (ifaceFqn.equals("org.apache.ibatis.annotations.Mapper") ||
                    ifaceFqn.equals("com.baomidou.mybatisplus.core.mapper.BaseMapper")) {
                    context.setMyBatisMapper(true);
                    if (context.getMybatisDetectionMethod().isEmpty()) {
                        context.setMybatisDetectionMethod("inheritance");
                    }
                    context.setMybatisMapperType("interface");
                    context.setMybatisMappingSource("annotation");
                }

                // Check if class implements Quartz Job interface (Phase 2.6)
                if (ifaceFqn.equals("org.quartz.Job") || ifaceFqn.equals("org.quartz.StatefulJob")) {
                    context.setQuartzJob(true);
                    logger.info("[QUARTZ_JOB] Class implements Quartz Job interface: {}", className);
                }
            }
        }

        super.visit(version, access, name, signature, superName, interfaces);
    }

    @Override
    public AnnotationVisitor visitAnnotation(String descriptor, boolean visible) {
        // Detect Spring stereotype annotations
        logger.info("[ANNOTATION_DETECTION] Processing annotation descriptor: {} for class {} (visible: {})",
                descriptor, context.getClassName(), visible);

        // Phase 1.3: Gradual migration to strategy pattern-based annotation handling
        // Use new AnnotationProcessor for class-level annotations when feature flag is enabled
        if (USE_NEW_ANNOTATION_PROCESSOR) {
            // Check if this is a class-level annotation we want to handle with the new processor
            boolean isHandledByNewProcessor = annotationProcessor.hasHandlerFor(descriptor);

            if (isHandledByNewProcessor) {
                // Use new processor-based handling
                boolean handled = annotationProcessor.processClassAnnotation(
                    descriptor, visible, context.getClassName(), context);

                if (handled) {
                    // Check if this annotation needs special attribute processing
                    if (needsAttributeVisitor(descriptor)) {
                        AnnotationVisitor parentAv = super.visitAnnotation(descriptor, visible);
                        return createAttributeVisitorFor(descriptor, parentAv);
                    } else {
                        // Simple flag annotation - just update class node
                        updateClassNode();
                        // Return super's visitor for ASM to continue processing
                        return super.visitAnnotation(descriptor, visible);
                    }
                }
            }
        }

        // Old code path (kept for backward compatibility and fallback)
        if (AnnotationConstants.COMPONENT.equals(descriptor)) {
            context.setSpringBeanType("component");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @Component detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.SERVICE.equals(descriptor)) {
            context.setSpringBeanType("service");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @Service detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.REPOSITORY.equals(descriptor)) {
            context.setSpringBeanType("repository");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @Repository detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.CONTROLLER.equals(descriptor)) {
            context.setSpringBeanType("controller");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @Controller detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.REST_CONTROLLER.equals(descriptor)) {
            context.setSpringBeanType("restController");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @RestController detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.CONFIGURATION.equals(descriptor)) {
            context.setSpringBeanType("configuration");
            context.setNeedsProxy(true);
            logger.info("[SPRING_DETECTION_SUCCESS] @Configuration detected on class {}", context.getClassName());
            updateClassNode(); 
            return createSpringBeanAnnotationVisitor(descriptor);
        } else if (AnnotationConstants.SCOPE.equals(descriptor)) {
            return new AnnotationVisitor(Opcodes.ASM9, super.visitAnnotation(descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("value".equals(name)) {
                        context.setSpringScope(value.toString());
                        updateClassNode();
                    }
                    super.visit(name, value);
                }

                @Override
                public void visitEnum(String name, String descriptor, String value) {
                    if ("value".equals(name)) {
                        context.setSpringScope(value);
                        updateClassNode();
                        logger.info("[SCOPE] Scope enum detected: {}", value);
                    }
                    super.visitEnum(name, descriptor, value);
                }
            };
        } else if (AnnotationConstants.PRIMARY.equals(descriptor)) {
            context.setPrimary(true);
            updateClassNode(); 
        } else if (AnnotationConstants.LAZY.equals(descriptor)) {
            context.setLazy(true);
            updateClassNode(); 
        } else if (AnnotationConstants.CONFIGURATION_PROPERTIES.equals(descriptor)) {
            return new AnnotationVisitor(Opcodes.ASM9, super.visitAnnotation(descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("prefix".equals(name) || "value".equals(name)) {
                        context.setConfigPropertiesPrefix(value.toString());
                        logger.info("[CONFIG_PROPERTIES] Class {} has @ConfigurationProperties with prefix: {}",
                                   context.getClassName(), context.getConfigPropertiesPrefix());
                    }
                    super.visit(name, value);
                }
            };
        } else if (AnnotationConstants.ASYNC.equals(descriptor)) {
            context.setClassAsync(true);
            context.setNeedsProxy(true);
            logger.info("[ASYNC] @Async detected on class {}", context.getClassName());

            return new AnnotationVisitor(Opcodes.ASM9, super.visitAnnotation(descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("value".equals(name)) {
                        context.setClassAsyncExecutor(value.toString());
                        logger.info("[ASYNC] Class {} has @Async with executor: {}", context.getClassName(), context.getClassAsyncExecutor());
                    }
                    super.visit(name, value);
                }
            };
        } else if (AnnotationConstants.VALUE.equals(descriptor)) {
            return new AnnotationVisitor(Opcodes.ASM9, super.visitAnnotation(descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("value".equals(name)) {
                        String configKey = extractConfigKey(value.toString());
                        if (configKey != null) {
                            logger.info("[CONFIG_VALUE] Class {} has @Value: {}", context.getClassName(), configKey);
                        }
                    }
                    super.visit(name, value);
                }
            };
        } else if (AnnotationConstants.SPRING_ASPECT.equals(descriptor) ||
                   AnnotationConstants.ASPECTJ_ASPECT.equals(descriptor)) {
            context.setAspect(true);
            context.setNeedsProxy(true);
            logger.info("[AOP] @Aspect detected on class {}", context.getClassName());
        }

        if (AnnotationConstants.MYBATIS_MAPPER.equals(descriptor)) {
            context.setMyBatisMapper(true);
            context.setMybatisDetectionMethod("annotation");
            context.setMybatisMapperType("annotation");
            context.setMybatisMappingSource("annotation");
        }

        if (AnnotationConstants.MAPSTRUCT_MAPPER.equals(descriptor)) {
            context.setMapStructMapper(true);
            context.setMyBatisMapper(false);
        }

        if (descriptor.startsWith(AnnotationConstants.MYBATIS_PLUS_PREFIX)) {
            logger.info("[MYBATIS_PLUS] Detected MyBatis Plus class annotation: {} on class {}", descriptor, context.getClassName());
        }

        // Detect class-level @RequestMapping
        if (AnnotationConstants.REQUEST_MAPPING.equals(descriptor)) {
            return new AnnotationVisitor(Opcodes.ASM9, super.visitAnnotation(descriptor, visible)) {
                @Override
                public void visit(String name, Object value) {
                    if ("value".equals(name) || "path".equals(name)) {
                        context.setClassBasePath(value.toString());
                    } else if ("method".equals(name)) {
                        context.setClassHttpMethod(value.toString());
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
                                }
                                super.visit(name, value);
                            }
                        };
                    }
                    return super.visitArray(name);
                }
            };
        }

        return super.visitAnnotation(descriptor, visible);
    }

    @Override
    public void visitEnd() {
        logger.info("[VISIT_END] Final update of class node for {}", context.getClassName());
        updateClassNode();
        super.visitEnd();
    }

    @Override
    public FieldVisitor visitField(int access, String name, String descriptor,
                                    String signature, Object value) {
        FieldVisitor fv = super.visitField(access, name, descriptor, signature, value);

        // Use the extracted FieldAnalyzer class with AnnotationProcessor
        return new FieldAnalyzer(context, annotationProcessor, context.getClassName(), name, descriptor, fv);
    }

    /**
     * Note: FieldAnalyzer has been extracted to visitors/FieldAnalyzer.java
     * This inner class has been removed as part of refactoring to reduce code complexity.
     * Phase 1.2: Extract FieldAnalyzer as independent class - COMPLETED
     */

    @Override
    public MethodVisitor visitMethod(int access, String name, String descriptor,
                                      String signature, String[] exceptions) {
        String methodFqn = context.getClassName() + "." + name + descriptorToSignature(descriptor);
        boolean isConstructor = name.equals("<init>");

        List<String> methodModifiers = parseModifiers(access);
        Type methodType = Type.getMethodType(descriptor);

        if (!isConstructor) {
            Type returnType = methodType.getReturnType();
            if (returnType.getSort() == Type.OBJECT || returnType.getSort() == Type.ARRAY) {
                String returnFqn = returnType.getClassName();
                if (!isPrimitive(returnFqn)) {
                    Map<String, Object> edge = new HashMap<>();
                    edge.put("edgeType", "member_of");
                    edge.put("fromFqn", returnFqn);
                    edge.put("toFqn", methodFqn);
                    edge.put("kind", "return");
                    context.addEdge(edge);
                }
            }
        }

        Type[] argumentTypes = methodType.getArgumentTypes();
        logger.info("[ARGS] Method {} has {} arguments", methodFqn, argumentTypes.length);
        List<String> methodParamTypes = new ArrayList<>();

        for (int i = 0; i < argumentTypes.length; i++) {
            Type argType = argumentTypes[i];
            String paramTypeName = getTypeName(argType);
            methodParamTypes.add(paramTypeName);

            if (argType.getSort() == Type.OBJECT || argType.getSort() == Type.ARRAY) {
                String argFqn = argType.getClassName();
                boolean primitive = isPrimitive(argFqn);
                if (!primitive) {
                    Map<String, Object> edge = new HashMap<>();
                    edge.put("edgeType", "member_of");
                    edge.put("fromFqn", argFqn);
                    edge.put("toFqn", methodFqn);
                    edge.put("kind", "argument");
                    context.addEdge(edge);
                } 
            }
        }

        String returnTypeName = "";
        if (!isConstructor) {
            Type returnTypeObj = methodType.getReturnType();
            returnTypeName = getTypeName(returnTypeObj);
        }

        // Use the extracted MethodAnalyzer class with AnnotationProcessor
        return new MethodAnalyzer(context, annotationProcessor, methodFqn, methodModifiers, isConstructor, methodParamTypes, returnTypeName, name, descriptor);
    }

    /**
     * Note: MethodAnalyzer has been extracted to visitors/MethodAnalyzer.java
     * This inner class has been removed as part of refactoring to reduce code complexity.
     * Phase 1.1: Extract MethodAnalyzer as independent class - COMPLETED
     */

    // --- Helper Methods ---

    /**
     * Checks if an annotation needs an AttributeVisitor for processing its attributes.
     *
     * @param descriptor The annotation descriptor
     * @return true if the annotation needs attribute processing
     */
    private boolean needsAttributeVisitor(String descriptor) {
        return AnnotationConstants.COMPONENT.equals(descriptor) ||
               AnnotationConstants.SERVICE.equals(descriptor) ||
               AnnotationConstants.REPOSITORY.equals(descriptor) ||
               AnnotationConstants.CONTROLLER.equals(descriptor) ||
               AnnotationConstants.REST_CONTROLLER.equals(descriptor) ||
               AnnotationConstants.CONFIGURATION.equals(descriptor) ||
               AnnotationConstants.SCOPE.equals(descriptor) ||
               AnnotationConstants.CONFIGURATION_PROPERTIES.equals(descriptor) ||
               AnnotationConstants.REQUEST_MAPPING.equals(descriptor) ||
               AnnotationConstants.ASYNC.equals(descriptor);
    }

    /**
     * Creates an AttributeVisitor for annotations that need attribute processing.
     *
     * @param descriptor The annotation descriptor
     * @param parentAv The parent annotation visitor
     * @return AnnotationVisitor for processing annotation attributes
     */
    private AnnotationVisitor createAttributeVisitorFor(String descriptor, AnnotationVisitor parentAv) {
        // Spring stereotype annotations - need to process bean name
        if (AnnotationConstants.COMPONENT.equals(descriptor) ||
            AnnotationConstants.SERVICE.equals(descriptor) ||
            AnnotationConstants.REPOSITORY.equals(descriptor) ||
            AnnotationConstants.CONTROLLER.equals(descriptor) ||
            AnnotationConstants.REST_CONTROLLER.equals(descriptor) ||
            AnnotationConstants.CONFIGURATION.equals(descriptor)) {
            return createSpringBeanAnnotationVisitorInternal(parentAv);
        }

        // @Scope - need to process scope value
        if (AnnotationConstants.SCOPE.equals(descriptor)) {
            return new com.webank.asmanalysis.asm.annotation.ScopeAnnotationHandler()
                .createAttributeVisitor(parentAv, context);
        }

        // @ConfigurationProperties - need to process prefix
        if (AnnotationConstants.CONFIGURATION_PROPERTIES.equals(descriptor)) {
            return new com.webank.asmanalysis.asm.annotation.ConfigurationPropertiesHandler()
                .createAttributeVisitor(parentAv, context);
        }

        // @RequestMapping - need to process path and method
        if (AnnotationConstants.REQUEST_MAPPING.equals(descriptor)) {
            return new com.webank.asmanalysis.asm.annotation.RequestMappingAnnotationHandler()
                .createAttributeVisitor(parentAv, context);
        }

        // @Async - need to process executor
        if (AnnotationConstants.ASYNC.equals(descriptor)) {
            return new com.webank.asmanalysis.asm.annotation.AsyncAnnotationHandler()
                .createAttributeVisitor(parentAv, context);
        }

        return parentAv;
    }

    /**
     * Internal method to create Spring bean annotation visitor.
     * Separated to allow reuse in the new annotation processing flow.
     */
    private AnnotationVisitor createSpringBeanAnnotationVisitorInternal(AnnotationVisitor parentAv) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    context.setSpringBeanName(value.toString());
                    updateClassNode();
                }
                super.visit(name, value);
            }
        };
    }

    private AnnotationVisitor createSpringBeanAnnotationVisitor(String descriptor) {
        return createSpringBeanAnnotationVisitorInternal(super.visitAnnotation(descriptor, true));
    }

    private List<String> parseModifiers(int access) {
        List<String> mods = new ArrayList<>();
        if ((access & Opcodes.ACC_PUBLIC) != 0) mods.add("public");
        if ((access & Opcodes.ACC_PRIVATE) != 0) mods.add("private");
        if ((access & Opcodes.ACC_PROTECTED) != 0) mods.add("protected");
        if ((access & Opcodes.ACC_STATIC) != 0) mods.add("static");
        if ((access & Opcodes.ACC_FINAL) != 0) mods.add("final");
        if ((access & Opcodes.ACC_ABSTRACT) != 0) mods.add("abstract");
        return mods;
    }

    private String descriptorToClassName(String descriptor) {
        Type type = Type.getType(descriptor);
        if (type.getSort() == Type.OBJECT || type.getSort() == Type.ARRAY) {
            return type.getClassName();
        }
        return null;
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

    private boolean isPrimitive(String className) {
        return className.equals("void") || className.equals("boolean") || className.equals("byte") ||
               className.equals("char") || className.equals("short") || className.equals("int") ||
               className.equals("long") || className.equals("float") || className.equals("double");
    }

    private String getTypeName(Type type) {
        switch (type.getSort()) {
            case Type.VOID: return "void";
            case Type.BOOLEAN: return "boolean";
            case Type.CHAR: return "char";
            case Type.BYTE: return "byte";
            case Type.SHORT: return "short";
            case Type.INT: return "int";
            case Type.FLOAT: return "float";
            case Type.LONG: return "long";
            case Type.DOUBLE: return "double";
            case Type.ARRAY: return getTypeName(type.getElementType()) + "[]";
            case Type.OBJECT: return type.getClassName();
            default: return type.getDescriptor();
        }
    }

    private String extractConfigKey(String value) {
        if (value == null || value.isEmpty()) return null;
        value = value.trim();
        if (value.startsWith("${") && value.endsWith("}")) {
            String key = value.substring(2, value.length() - 1);
            int colonIndex = key.indexOf(':');
            if (colonIndex > 0) key = key.substring(0, colonIndex).trim();
            return key;
        }
        return null;
    }

    /**
     * Phase 2.3: Refactored updateClassNode method.
     * This method now delegates to specialized sub-methods, each handling a specific concern.
     */
    private void updateClassNode() {
        if (context.getClassNode() == null) {
            logger.warn("[UPDATE_CLASS_NODE] classNode is null, cannot update");
            return;
        }

        // Phase 2.3: Call specialized sub-methods for each concern
        generateSpringBeanNameIfMissing();
        updateClassNodeAttributes();
        updateSpringBeanInfo();
        updateMyBatisMapperInfo();
        updateConfigurationProperties();
        updateAopInfo();
        updateAsyncInfo();
        updateProxyInfo();
        updateQuartzJobInfo();
    }

    // ========== Phase 2.3: Refactored updateClassNode sub-methods ==========

    /**
     * Phase 2.3: Generate default Spring bean name if not explicitly set.
     */
    private void generateSpringBeanNameIfMissing() {
        if (context.getSpringBeanType() != null && context.getSpringBeanName() == null) {
            String simpleName = context.getClassName().substring(context.getClassName().lastIndexOf('.') + 1);
            if (simpleName.length() > 0) {
                String beanName = Character.toLowerCase(simpleName.charAt(0)) + simpleName.substring(1);
                if (simpleName.length() > 1 && Character.isUpperCase(simpleName.charAt(1)) && Character.isUpperCase(simpleName.charAt(0))) {
                    beanName = simpleName;
                }
                context.setSpringBeanName(beanName);
            }
        }
    }

    /**
     * Phase 2.3: Initialize class node attributes map if not present.
     */
    private void updateClassNodeAttributes() {
        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");
        if (attributes == null) {
            attributes = new HashMap<>();
            classNode.put("attributes", attributes);
        }
    }

    /**
     * Phase 2.3: Update Spring bean information in class node.
     */
    private void updateSpringBeanInfo() {
        if (context.getSpringBeanType() == null) {
            return;
        }

        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");

        classNode.put("springBeanType", context.getSpringBeanType());
        classNode.put("springBeanName", context.getSpringBeanName());
        classNode.put("springScope", context.getSpringScope());
        classNode.put("springPrimary", context.isPrimary());
        classNode.put("springLazy", context.isLazy());

        attributes.put("spring_bean", true);
        if (context.getSpringBeanName() != null) {
            attributes.put("spring_bean_name", context.getSpringBeanName());
        }
        if (!"singleton".equals(context.getSpringScope())) {
            attributes.put("spring_scope", context.getSpringScope());
        }
        if (context.isPrimary()) {
            attributes.put("spring_primary", true);
        }
        if (context.isLazy()) {
            attributes.put("spring_lazy", true);
        }
    }

    /**
     * Phase 2.3: Update MyBatis mapper information in class node.
     */
    private void updateMyBatisMapperInfo() {
        Map<String, Object> classNode = context.getClassNode();
        if (!classNode.containsKey("isMyBatisMapper") || !(Boolean) classNode.get("isMyBatisMapper")) {
            return;
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");
        attributes.put("mybatis_mapper", true);

        if (classNode.containsKey("mybatisMapperType")) {
            attributes.put("mybatis_mapper_type", classNode.get("mybatisMapperType"));
        }
        if (classNode.containsKey("mybatisMappingSource")) {
            attributes.put("mybatis_mapping_source", classNode.get("mybatisMappingSource"));
        }
    }

    /**
     * Phase 2.3: Update configuration properties information in class node.
     */
    private void updateConfigurationProperties() {
        Map<String, Object> classNode = context.getClassNode();

        if (context.getConfigPropertiesPrefix() != null) {
            classNode.put("configPropertiesPrefix", context.getConfigPropertiesPrefix());
        }
        if (!context.getConfigUsages().isEmpty()) {
            classNode.put("configUsages", new ArrayList<>(context.getConfigUsages()));
        }
    }

    /**
     * Phase 2.3: Update AOP information in class node.
     */
    private void updateAopInfo() {
        if (!context.isAspect()) {
            return;
        }

        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");

        classNode.put("isAspect", true);
        attributes.put("aspect", true);
    }

    /**
     * Phase 2.3: Update async information in class node.
     */
    private void updateAsyncInfo() {
        if (!context.isClassAsync()) {
            return;
        }

        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");

        classNode.put("isClassAsync", true);
        if (!context.getClassAsyncExecutor().isEmpty()) {
            classNode.put("classAsyncExecutor", context.getClassAsyncExecutor());
            attributes.put("class_async_executor", context.getClassAsyncExecutor());
        }
        attributes.put("class_async", true);
    }

    /**
     * Phase 2.3: Update proxy information in class node.
     */
    private void updateProxyInfo() {
        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");

        classNode.put("isFinalClass", context.isFinalClass());
        classNode.put("hasInterfaces", context.hasInterfaces());
        classNode.put("needsProxy", context.isNeedsProxy());

        if (context.isFinalClass()) {
            attributes.put("final_class", true);
        }
        if (context.hasInterfaces()) {
            attributes.put("has_interfaces", true);
        }
        if (context.isNeedsProxy()) {
            attributes.put("needs_proxy", true);
        }

        if (context.isNeedsProxy()) {
            String proxyType;
            if (context.isFinalClass()) {
                proxyType = "cglib";
            } else if (context.hasInterfaces()) {
                proxyType = "jdk_or_cglib";
            } else {
                proxyType = "cglib";
            }
            context.setProxyType(proxyType);
            classNode.put("proxyType", proxyType);
            attributes.put("proxy_type", proxyType);
        }
    }

    /**
     * Phase 2.3: Update Quartz job information in class node.
     */
    private void updateQuartzJobInfo() {
        if (!context.isQuartzJob() && !context.isExtendsQuartzJobBean()) {
            return;
        }

        Map<String, Object> classNode = context.getClassNode();
        @SuppressWarnings("unchecked")
        Map<String, Object> attributes = (Map<String, Object>) classNode.get("attributes");

        if (context.isQuartzJob()) {
            classNode.put("isQuartzJob", true);
            attributes.put("quartz_job", true);
        }
        if (context.isExtendsQuartzJobBean()) {
            classNode.put("extendsQuartzJobBean", true);
            attributes.put("extends_quartz_job_bean", true);
        }
    }
}