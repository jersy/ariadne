package com.webank.asmanalysis.asm.annotation;

import com.webank.asmanalysis.asm.AnnotationConstants;
import com.webank.asmanalysis.asm.AnalysisContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Handler for @Mapper annotation (MapStruct).
 *
 * <p>Processes MapStruct @Mapper annotation to identify mapper interfaces.
 * Distinguished from MyBatis @Mapper by checking the package name.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MapStructMapperAnnotationHandler implements ClassAnnotationHandler {
    private static final Logger logger = LoggerFactory.getLogger(MapStructMapperAnnotationHandler.class);

    @Override
    public boolean canHandle(String descriptor) {
        return AnnotationConstants.MAPSTRUCT_MAPPER.equals(descriptor);
    }

    @Override
    public void handleClass(ClassAnnotationContext context) {
        AnalysisContext analysisContext = context.getAnalysisContext();
        analysisContext.setMapStructMapper(true);
        analysisContext.setMyBatisMapper(false); // Clear MyBatis mapper flag

        logger.info("[MAPSTRUCT_MAPPER_HANDLER] @Mapper (MapStruct) detected on class {}",
            context.getClassName());
    }

    @Override
    public int getPriority() {
        return 87; // High priority, slightly lower than MyBatis to allow MyBatis first check
    }
}
