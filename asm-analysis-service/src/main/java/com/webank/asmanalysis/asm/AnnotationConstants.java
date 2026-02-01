package com.webank.asmanalysis.asm;

/**
 * Constants for annotation descriptors used in ASM analysis.
 */
public final class AnnotationConstants {
    private AnnotationConstants() {}

    // Spring Stereotypes
    public static final String COMPONENT = "Lorg/springframework/stereotype/Component;";
    public static final String SERVICE = "Lorg/springframework/stereotype/Service;";
    public static final String REPOSITORY = "Lorg/springframework/stereotype/Repository;";
    public static final String CONTROLLER = "Lorg/springframework/stereotype/Controller;";
    public static final String REST_CONTROLLER = "Lorg/springframework/web/bind/annotation/RestController;";
    public static final String CONFIGURATION = "Lorg/springframework/context/annotation/Configuration;";

    // Spring Context
    public static final String SCOPE = "Lorg/springframework/context/annotation/Scope;";
    public static final String PRIMARY = "Lorg/springframework/context/annotation/Primary;";
    public static final String LAZY = "Lorg/springframework/context/annotation/Lazy;";
    public static final String CONFIGURATION_PROPERTIES = "Lorg/springframework/boot/context/properties/ConfigurationProperties;";
    public static final String BEAN = "Lorg/springframework/context/annotation/Bean;";
    public static final String DEPENDS_ON = "Lorg/springframework/context/annotation/DependsOn;";

    // Dependency Injection
    public static final String AUTOWIRED = "Lorg/springframework/beans/factory/annotation/Autowired;";
    public static final String VALUE = "Lorg/springframework/beans/factory/annotation/Value;";
    public static final String QUALIFIER = "Lorg/springframework/beans/factory/annotation/Qualifier;";
    public static final String INJECT = "Ljavax/inject/Inject;";
    public static final String RESOURCE = "Ljavax/annotation/Resource;";

    // Spring MVC
    public static final String REQUEST_MAPPING = "Lorg/springframework/web/bind/annotation/RequestMapping;";
    public static final String GET_MAPPING = "Lorg/springframework/web/bind/annotation/GetMapping;";
    public static final String POST_MAPPING = "Lorg/springframework/web/bind/annotation/PostMapping;";
    public static final String PUT_MAPPING = "Lorg/springframework/web/bind/annotation/PutMapping;";
    public static final String DELETE_MAPPING = "Lorg/springframework/web/bind/annotation/DeleteMapping;";
    public static final String PATCH_MAPPING = "Lorg/springframework/web/bind/annotation/PatchMapping;";
    public static final String CONTROLLER_ADVICE = "Lorg/springframework/web/bind/annotation/ControllerAdvice;";
    public static final String CROSS_ORIGIN = "Lorg/springframework/web/bind/annotation/CrossOrigin;";
    public static final String RESPONSE_STATUS = "Lorg/springframework/web/bind/annotation/ResponseStatus;";

    // Async & Scheduling
    public static final String ASYNC = "Lorg/springframework/scheduling/annotation/Async;";
    public static final String SCHEDULED = "Lorg/springframework/scheduling/annotation/Scheduled;";

    // AOP
    public static final String SPRING_ASPECT = "Lorg/springframework/aop/aspectj/annotation/Aspect;";
    public static final String ASPECTJ_ASPECT = "Lorg/aspectj/lang/annotation/Aspect;";
    public static final String BEFORE = "Lorg/aspectj/lang/annotation/Before;";
    public static final String AFTER = "Lorg/aspectj/lang/annotation/After;";
    public static final String AROUND = "Lorg/aspectj/lang/annotation/Around;";
    public static final String AFTER_RETURNING = "Lorg/aspectj/lang/annotation/AfterReturning;";
    public static final String AFTER_THROWING = "Lorg/aspectj/lang/annotation/AfterThrowing;";
    public static final String POINTCUT = "Lorg/aspectj/lang/annotation/Pointcut;";
    public static final String ORDER = "Lorg/springframework/core/annotation/Order;";

    // Transaction
    public static final String SPRING_TRANSACTIONAL = "Lorg/springframework/transaction/annotation/Transactional;";
    public static final String JAVAX_TRANSACTIONAL = "Ljavax/transaction/Transactional;";
    public static final String JAKARTA_TRANSACTIONAL = "Ljakarta/transaction/Transactional;";

    // MyBatis
    public static final String MYBATIS_MAPPER = "Lorg/apache/ibatis/annotations/Mapper;";
    public static final String MYBATIS_SELECT = "Lorg/apache/ibatis/annotations/Select;";
    public static final String MYBATIS_INSERT = "Lorg/apache/ibatis/annotations/Insert;";
    public static final String MYBATIS_UPDATE = "Lorg/apache/ibatis/annotations/Update;";
    public static final String MYBATIS_DELETE = "Lorg/apache/ibatis/annotations/Delete;";
    public static final String MYBATIS_SELECT_PROVIDER = "Lorg/apache/ibatis/annotations/SelectProvider;";
    public static final String MYBATIS_INSERT_PROVIDER = "Lorg/apache/ibatis/annotations/InsertProvider;";
    public static final String MYBATIS_UPDATE_PROVIDER = "Lorg/apache/ibatis/annotations/UpdateProvider;";
    public static final String MYBATIS_DELETE_PROVIDER = "Lorg/apache/ibatis/annotations/DeleteProvider;";
    public static final String MYBATIS_OPTIONS = "Lorg/apache/ibatis/annotations/Options;";

    // MyBatis Plus
    public static final String MYBATIS_PLUS_PREFIX = "Lcom/baomidou/mybatisplus/annotation/";
    public static final String MYBATIS_PLUS_TABLE_NAME = "Lcom/baomidou/mybatisplus/annotation/TableName;";

    // MapStruct
    public static final String MAPSTRUCT_MAPPER = "Lorg/mapstruct/Mapper;";

    // Standard
    public static final String OVERRIDE = "Ljava/lang/Override;";
}