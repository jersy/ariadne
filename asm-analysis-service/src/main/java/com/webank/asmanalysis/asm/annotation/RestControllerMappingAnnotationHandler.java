package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for REST mapping annotations.
 *
 * <p>Handles Spring MVC REST mapping annotations:
 * @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @PatchMapping
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class RestControllerMappingAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(RestControllerMappingAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.GET_MAPPING.equals(descriptor) ||
               AnnotationConstants.POST_MAPPING.equals(descriptor) ||
               AnnotationConstants.PUT_MAPPING.equals(descriptor) ||
               AnnotationConstants.DELETE_MAPPING.equals(descriptor) ||
               AnnotationConstants.PATCH_MAPPING.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Extract HTTP method from annotation descriptor
        String httpMethod = extractHttpMethod(context.getDescriptor());

        // Mark as REST endpoint
        methodNode.put("isRestEndpoint", true);
        methodNode.put("httpMethod", httpMethod);
        methodNode.put("isEntryPoint", true);
        methodNode.put("entryPointType", "rest_endpoint");

        logger.info("[REST_MAPPING_HANDLER] @{} detected on method {}",
            httpMethod, context.getMethodFqn());
    }

    /**
     * Extracts HTTP method name from annotation descriptor.
     */
    private String extractHttpMethod(String descriptor) {
        if (AnnotationConstants.GET_MAPPING.equals(descriptor)) {
            return "GET";
        } else if (AnnotationConstants.POST_MAPPING.equals(descriptor)) {
            return "POST";
        } else if (AnnotationConstants.PUT_MAPPING.equals(descriptor)) {
            return "PUT";
        } else if (AnnotationConstants.DELETE_MAPPING.equals(descriptor)) {
            return "DELETE";
        } else if (AnnotationConstants.PATCH_MAPPING.equals(descriptor)) {
            return "PATCH";
        }
        return "UNKNOWN";
    }

    @Override
    public int getPriority() {
        return 93; // Very high priority for REST endpoints
    }
}
