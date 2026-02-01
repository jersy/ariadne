package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for MyBatis Plus annotations.
 *
 * <p>Handles various MyBatis Plus annotations like @TableName, @TableId, etc.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MyBatisPlusAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(MyBatisPlusAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return descriptor.startsWith(AnnotationConstants.MYBATIS_PLUS_PREFIX);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();

        logger.info("[MYBATIS_PLUS_HANDLER] MyBatis Plus annotation {} detected on class {}",
            context.getDescriptor(), context.getClassName());
    }

    @Override
    public int getPriority() {
        return 72; // Medium-high priority for ORM framework
    }
}
