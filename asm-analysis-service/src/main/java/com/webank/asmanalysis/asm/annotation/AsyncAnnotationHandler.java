package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Handler for @Async annotation.
 *
 * <p>Supports both class-level and method-level @Async annotations.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class AsyncAnnotationHandler implements ClassAnnotationHandler, MethodAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(AsyncAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.ASYNC.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        // Class-level @Async - mark class as async
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setClassAsync(true);
        analysisContext.setNeedsProxy(true);

        logger.info("[ASYNC_CLASS] @Async on class {}", context.getClassName());
    }

    @Override
    public void handleMethod(MethodAnnotationContext context) {
        Map<String, Object> methodNode = context.getMethodNode();
        methodNode.put("isAsync", true);
        context.getAnalysisContext().setNeedsProxy(true);

        logger.debug("[ASYNC_METHOD] @Async on method {}", context.getMethodFqn());
    }

    /**
     * Creates an AnnotationVisitor to process @Async attributes.
     *
     * @param parentAv The parent annotation visitor
     * @param context The analysis context
     * @return AnnotationVisitor for processing async attributes
     */
    public AnnotationVisitor createAttributeVisitor(
        AnnotationVisitor parentAv,
        AnalysisContext context
    ) {
        return new AnnotationVisitor(Opcodes.ASM9, parentAv) {
            @Override
            public void visit(String name, Object value) {
                if ("value".equals(name)) {
                    context.setClassAsyncExecutor(value.toString());
                    logger.info("[ASYNC] Class {} has @Async with executor: {}",
                        context.getClassName(), value);
                }
                super.visit(name, value);
            }
        };
    }

    @Override
    public int getPriority() {
        return 85; // High priority for async processing
    }
}
