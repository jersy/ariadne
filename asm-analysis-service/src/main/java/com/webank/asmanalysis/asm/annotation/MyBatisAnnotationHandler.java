package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for MyBatis annotations (@Select, @Insert, @Update, @Delete, etc.).
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MyBatisAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(MyBatisAnnotationHandler.class);

    private static final String MYBATIS_ANNOTATION_PREFIX = "Lorg/apache/ibatis/annotations/";

    @Override
    public boolean canHandle(String descriptor) {
        return descriptor.startsWith(MYBATIS_ANNOTATION_PREFIX) ||
               descriptor.startsWith(AnnotationConstants.MYBATIS_PLUS_PREFIX);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();
        String descriptor = context.getDescriptor();

        methodNode.put("hasMyBatisAnnotation", true);
        methodNode.put("mybatisAnnotationDescriptor", descriptor);

        String operationType = extractOperationType(descriptor);
        methodNode.put("mybatisOperationType", operationType);

        logger.debug("[MYBATIS] {} annotation on method {}", operationType, context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 75; // Medium priority for MyBatis annotations
    }

    /**
     * Extracts the operation type from the annotation descriptor.
     */
    private String extractOperationType(String descriptor) {
        if (descriptor.contains("Select")) {
            return "select";
        } else if (descriptor.contains("Insert")) {
            return "insert";
        } else if (descriptor.contains("Update")) {
            return "update";
        } else if (descriptor.contains("Delete")) {
            return "delete";
        } else if (descriptor.contains("Provider")) {
            return "provider";
        } else if (descriptor.contains("Result") || descriptor.contains("Results")) {
            return "results";
        } else if (descriptor.startsWith(AnnotationConstants.MYBATIS_PLUS_PREFIX)) {
            return "mybatis_plus";
        }
        return "other";
    }
}
