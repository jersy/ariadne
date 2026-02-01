package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for AOP annotations (@Before, @After, @Around, @AfterReturning, @AfterThrowing, @Pointcut).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class AopAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(AopAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.BEFORE.equals(descriptor) ||
               AnnotationConstants.AFTER.equals(descriptor) ||
               AnnotationConstants.AROUND.equals(descriptor) ||
               AnnotationConstants.AFTER_RETURNING.equals(descriptor) ||
               AnnotationConstants.AFTER_THROWING.equals(descriptor) ||
               AnnotationConstants.POINTCUT.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();
        String adviceType = extractAdviceType(context.getDescriptor());

        methodNode.put("adviceType", adviceType);
        methodNode.put("isAopAdvice", true);

        logger.debug("[AOP_ADVICE] {} on method {}", adviceType, context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 80; // Medium-high priority for AOP annotations
    }

    /**
     * Extracts the advice type from the annotation descriptor.
     */
    private String extractAdviceType(String descriptor) {
        if (AnnotationConstants.BEFORE.equals(descriptor)) {
            return "@Before";
        } else if (AnnotationConstants.AFTER.equals(descriptor)) {
            return "@After";
        } else if (AnnotationConstants.AROUND.equals(descriptor)) {
            return "@Around";
        } else if (AnnotationConstants.AFTER_RETURNING.equals(descriptor)) {
            return "@AfterReturning";
        } else if (AnnotationConstants.AFTER_THROWING.equals(descriptor)) {
            return "@AfterThrowing";
        } else if (AnnotationConstants.POINTCUT.equals(descriptor)) {
            return "@Pointcut";
        }
        return "Unknown";
    }
}
