package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Mapper annotation (MyBatis).
 *
 * <p>Processes MyBatis @Mapper annotation to identify mapper interfaces.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MyBatisMapperAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(MyBatisMapperAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.MYBATIS_MAPPER.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setMyBatisMapper(true);
        analysisContext.setMybatisDetectionMethod("annotation");
        analysisContext.setMybatisMapperType("annotation");
        analysisContext.setMybatisMappingSource("annotation");

        logger.info("[MYBATIS_MAPPER_HANDLER] @Mapper detected on class {}",
            context.getClassName());
    }

    @Override
    public int getPriority() {
        return 88; // High priority for persistence layer
    }
}
