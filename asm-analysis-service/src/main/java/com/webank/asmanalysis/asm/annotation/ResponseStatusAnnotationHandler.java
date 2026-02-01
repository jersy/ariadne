package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @ResponseStatus annotation.
 *
 * <p>Handles Spring @ResponseStatus annotation for specifying HTTP response status codes.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ResponseStatusAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ResponseStatusAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.RESPONSE_STATUS.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark method as having response status specification
        methodNode.put("hasResponseStatus", true);

        logger.debug("[RESPONSE_STATUS_HANDLER] @ResponseStatus detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 56; // Medium priority for response status configuration
    }
}
