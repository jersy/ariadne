package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Transactional annotation.
 *
 * <p>Supports both class-level and method-level @Transactional annotations.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class TransactionalHandler implements ClassAnnotationHandler, MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(TransactionalHandler.class);

    private static final String TRANSACTIONAL_DESC =
        "Lorg/springframework/transaction/annotation/Transactional;";

    @Override
    public boolean canHandle(String descriptor) {
        return TRANSACTIONAL_DESC.equals(descriptor) ||
               AnnotationConstants.JAVAX_TRANSACTIONAL.equals(descriptor) ||
               AnnotationConstants.JAKARTA_TRANSACTIONAL.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        // Class-level @Transactional - mark class as transactional
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setNeedsProxy(true);

        logger.info("[TRANSACTIONAL_CLASS] @Transactional on class {}",
            context.getClassName());
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        // Method-level @Transactional - mark the method as transactional
        Map<String, Object> methodNode = context.getMethodNode();
        methodNode.put("isTransactional", true);
        context.getAnalysisContext().setNeedsProxy(true);

        logger.debug("[TRANSACTIONAL_METHOD] @Transactional on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 90; // High priority for core transaction annotation
    }
}
