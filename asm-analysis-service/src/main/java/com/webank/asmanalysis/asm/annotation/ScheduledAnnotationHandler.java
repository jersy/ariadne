package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Scheduled annotation.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ScheduledAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(ScheduledAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.SCHEDULED.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark as scheduled and entry point
        methodNode.put("isScheduled", true);
        methodNode.put("isEntryPoint", true);
        methodNode.put("entryPointType", "spring_scheduled");

        logger.info("[SCHEDULED] @Scheduled on method {}", context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 70; // Medium priority for scheduled annotations
    }
}
