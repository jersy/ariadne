package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Bean annotation.
 *
 * <p>Handles Spring @Bean annotation at method level in @Configuration classes.
 * Identifies methods that create beans.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class BeanAnnotationHandler implements MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(BeanAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.BEAN.equals(descriptor);
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();

        // Mark method as bean creation method
        methodNode.put("isBean", true);
        methodNode.put("beanCreationMethod", true);
        methodNode.put("entryPointType", "spring_bean");

        // Mark as entry point since bean creation methods can be called
        methodNode.put("isEntryPoint", true);

        context.getAnalysisContext().setNeedsProxy(true);

        logger.info("[BEAN_HANDLER] @Bean detected on method {}",
            context.getMethodFqn());
    }

    @Override
    public int getPriority() {
        return 92; // Very high priority for bean definition
    }
}
