package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Set;

/**
 * Handler for Spring Bean annotations (@Component, @Service, @Repository, @Controller, @RestController).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class SpringBeanAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(SpringBeanAnnotationHandler.class);

    private static final Set<String> SUPPORTED_ANNOTATIONS = Set.of(
        AnnotationConstants.COMPONENT,
        AnnotationConstants.SERVICE,
        AnnotationConstants.REPOSITORY,
        AnnotationConstants.CONTROLLER,
        AnnotationConstants.REST_CONTROLLER
    );

    @Override
    public boolean canHandle(String descriptor) {
        return SUPPORTED_ANNOTATIONS.contains(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        String beanType = extractBeanType(context.getDescriptor());

        analysisContext.setSpringBeanType(beanType);
        analysisContext.setNeedsProxy(true);

        logger.info("[SPRING_DETECTION_SUCCESS] @{} detected on class {}",
            beanType, context.getClassName());
    }

    @Override
    public int getPriority() {
        return 100; // High priority for core Spring annotations
    }

    /**
     * Extracts the bean type from the annotation descriptor.
     * Example: "Lorg/springframework/stereotype/Service;" -> "service"
     */
    private String extractBeanType(String descriptor) {
        if (AnnotationConstants.REST_CONTROLLER.equals(descriptor)) {
            return "rest_controller";
        }

        // Extract simple name from descriptor and convert to lowercase
        return descriptor.substring(
            descriptor.lastIndexOf('/') + 1,
            descriptor.length() - 1
        ).toLowerCase();
    }
}
