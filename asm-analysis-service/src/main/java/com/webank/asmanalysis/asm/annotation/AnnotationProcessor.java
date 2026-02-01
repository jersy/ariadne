package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Coordinator for annotation processing using the strategy pattern.
 *
 * <p>This class manages all registered annotation handlers and delegates
 * annotation processing to the appropriate handler based on the annotation descriptor.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class AnnotationProcessor {
    private static final Logger logger = LoggerFactory.getLogger(AnnotationProcessor.class);

    private final List<ClassAnnotationHandler> classHandlers;
    private final List<MethodAnnotationHandler> methodHandlers;
    private final List<FieldAnnotationHandler> fieldHandlers;

    /**
     * Creates a new AnnotationProcessor with the given analysis context.
     * Automatically registers all available annotation handlers.
     *
     * @param context The shared analysis context
     */
    public AnnotationProcessor(AnalysisContext context) {
        this.classHandlers = new ArrayList<>();
        this.methodHandlers = new ArrayList<>();
        this.fieldHandlers = new ArrayList<>();
        registerHandlers();
        sortHandlers();
    }

    /**
     * Registers all annotation handlers.
     */
    private void registerHandlers() {
        // Class-level handlers - ordered by priority
        classHandlers.add(new SpringBeanAnnotationHandler());           // Priority: 100
        classHandlers.add(new ControllerAdviceAnnotationHandler());     // Priority: 98
        classHandlers.add(new AspectAnnotationHandler());               // Priority: 95
        classHandlers.add(new TransactionalHandler());                  // Priority: 90
        classHandlers.add(new MyBatisMapperAnnotationHandler());        // Priority: 88
        classHandlers.add(new MapStructMapperAnnotationHandler());      // Priority: 87
        classHandlers.add(new AsyncAnnotationHandler());                // Priority: 85
        classHandlers.add(new RequestMappingAnnotationHandler());       // Priority: 80
        classHandlers.add(new ConfigurationPropertiesHandler());        // Priority: 75
        classHandlers.add(new MyBatisPlusAnnotationHandler());          // Priority: 72
        classHandlers.add(new PrimaryAnnotationHandler());              // Priority: 65
        classHandlers.add(new ScopeAnnotationHandler());                // Priority: 60
        classHandlers.add(new CrossOriginAnnotationHandler());          // Priority: 58
        classHandlers.add(new LazyAnnotationHandler());                 // Priority: 55
        classHandlers.add(new OrderAnnotationHandler());                // Priority: 50

        // Method-level handlers - ordered by priority
        methodHandlers.add(new RestControllerMappingAnnotationHandler());  // Priority: 93
        methodHandlers.add(new BeanAnnotationHandler());                   // Priority: 92
        methodHandlers.add(new TransactionalHandler());                    // Priority: 90
        methodHandlers.add(new AsyncAnnotationHandler());                   // Priority: 85
        methodHandlers.add(new AopAnnotationHandler());                    // Priority: 80
        methodHandlers.add(new PointcutAnnotationHandler());               // Priority: 78
        methodHandlers.add(new MyBatisAnnotationHandler());                // Priority: 75
        methodHandlers.add(new ScheduledAnnotationHandler());              // Priority: 70
        methodHandlers.add(new DependsOnAnnotationHandler());              // Priority: 68
        methodHandlers.add(new CrossOriginAnnotationHandler());            // Priority: 58
        methodHandlers.add(new ResponseStatusAnnotationHandler());         // Priority: 56
        methodHandlers.add(new OrderAnnotationHandler());                  // Priority: 50

        // Field-level handlers - ordered by priority
        fieldHandlers.add(new AutowiredAnnotationHandler());    // Priority: 95
        fieldHandlers.add(new ValueAnnotationHandler());        // Priority: 93
        fieldHandlers.add(new InjectAnnotationHandler());       // Priority: 92
        fieldHandlers.add(new ResourceAnnotationHandler());     // Priority: 91
        fieldHandlers.add(new QualifierAnnotationHandler());    // Priority: 90

        logger.info("[ANNOTATION_PROCESSOR] Registered {} class handlers, {} method handlers, {} field handlers",
            classHandlers.size(), methodHandlers.size(), fieldHandlers.size());
    }

    /**
     * Sorts handlers by priority (descending).
     */
    private void sortHandlers() {
        classHandlers.sort(Comparator.comparingInt(ClassAnnotationHandler::getPriority).reversed());
        methodHandlers.sort(Comparator.comparingInt(MethodAnnotationHandler::getPriority).reversed());
        fieldHandlers.sort(Comparator.comparingInt(FieldAnnotationHandler::getPriority).reversed());
    }

    /**
     * Processes a class-level annotation.
     *
     * @param descriptor The annotation descriptor
     * @param visible Whether the annotation is visible at runtime
     * @param className The class name
     * @param context The analysis context
     * @return true if a handler was found and executed
     */
    public boolean processClassAnnotation(
        String descriptor,
        boolean visible,
        String className,
        AnalysisContext context
    ) {
        ClassAnnotationContext ctx = new ClassAnnotationContext(context, descriptor, visible, className);

        for (ClassAnnotationHandler handler : classHandlers) {
            if (handler.canHandle(descriptor)) {
                handler.handleClass(ctx);
                return true;
            }
        }

        return false;
    }

    /**
     * Processes a method-level annotation.
     *
     * @param descriptor The annotation descriptor
     * @param visible Whether the annotation is visible at runtime
     * @param methodNode The method node map
     * @param context The analysis context
     * @return true if a handler was found and executed
     */
    public boolean processMethodAnnotation(
        String descriptor,
        boolean visible,
        java.util.Map<String, Object> methodNode,
        AnalysisContext context
    ) {
        MethodAnnotationContext ctx = new MethodAnnotationContext(context, descriptor, visible, methodNode);

        for (MethodAnnotationHandler handler : methodHandlers) {
            if (handler.canHandle(descriptor)) {
                handler.handleMethod(ctx);
                return true;
            }
        }

        return false;
    }

    /**
     * Processes a field-level annotation.
     *
     * @param descriptor The annotation descriptor
     * @param visible Whether the annotation is visible at runtime
     * @param className The class name
     * @param fieldName The field name
     * @param context The analysis context
     * @return true if a handler was found and executed
     */
    public boolean processFieldAnnotation(
        String descriptor,
        boolean visible,
        String className,
        String fieldName,
        AnalysisContext context
    ) {
        FieldAnnotationContext ctx = new FieldAnnotationContext(context, descriptor, visible, className, fieldName);

        for (FieldAnnotationHandler handler : fieldHandlers) {
            if (handler.canHandle(descriptor)) {
                handler.handleField(ctx);
                return true;
            }
        }

        return false;
    }

    /**
     * Checks if any registered handler can handle the given annotation.
     *
     * @param descriptor The annotation descriptor
     * @return true if a handler exists for this annotation
     */
    public boolean hasHandlerFor(String descriptor) {
        return classHandlers.stream().anyMatch(h -> h.canHandle(descriptor)) ||
               methodHandlers.stream().anyMatch(h -> h.canHandle(descriptor)) ||
               fieldHandlers.stream().anyMatch(h -> h.canHandle(descriptor));
    }
}
