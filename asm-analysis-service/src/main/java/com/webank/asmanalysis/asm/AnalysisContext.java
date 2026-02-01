package com.webank.asmanalysis.asm;

import java.nio.file.Path;
import java.util.*;

/**
 * 上下文对象，用于存储单次类分析过程中的所有状态数据。
 * 将数据模型从 ASM 的访问者逻辑中剥离出来。
 */
public class AnalysisContext {
    private final Path classFile;

    // 图数据 (Graph Data)
    private final List<Map<String, Object>> nodes = new ArrayList<>();
    private final List<Map<String, Object>> edges = new ArrayList<>();
    private Map<String, Object> classNode; // 对主类节点的引用

    // 类基本信息 (Class Basic Info)
    private String className;
    private boolean isInterface;
    private boolean isEnum;
    private boolean isAbstract;
    private boolean isFinalClass;
    private boolean hasInterfaces;
    private List<String> modifiers;
    private String classBasePath = "";
    private String classHttpMethod = "";

    // Spring 元数据 (Spring Metadata)
    private String springBeanType = null; // component, service, etc.
    private String springBeanName = null;
    private String springScope = "singleton";
    private boolean isPrimary = false;
    private boolean isLazy = false;

    // MyBatis / MapStruct
    private boolean isMyBatisMapper = false;
    private boolean isMapStructMapper = false;
    private String mybatisDetectionMethod = "";
    private String mybatisMapperType = "";
    private String mybatisMappingSource = "";

    // 配置属性 (Configuration)
    private String configPropertiesPrefix = null;
    private final List<Map<String, Object>> configUsages = new ArrayList<>();

    // AOP / 代理 / 异步 (AOP / Proxy / Async)
    private boolean isAspect = false;
    private boolean isClassAsync = false;
    private String classAsyncExecutor = "";
    private boolean needsProxy = false;
    private String proxyType = null; // cglib, jdk_or_cglib, unknown

    // Quartz
    private boolean isQuartzJob = false;
    private boolean extendsQuartzJobBean = false;

    public AnalysisContext(Path classFile) {
        this.classFile = classFile;
    }

    // --- Graph Operations ---

    public void addNode(Map<String, Object> node) {
        this.nodes.add(node);
    }

    public void addEdge(Map<String, Object> edge) {
        this.edges.add(edge);
    }

    public void addConfigUsage(Map<String, Object> usage) {
        this.configUsages.add(usage);
    }

    // --- Getters & Setters ---

    public Path getClassFile() { return classFile; }
    public List<Map<String, Object>> getNodes() { return nodes; }
    public List<Map<String, Object>> getEdges() { return edges; }
    public List<Map<String, Object>> getConfigUsages() { return configUsages; }

    public Map<String, Object> getClassNode() { return classNode; }
    public void setClassNode(Map<String, Object> classNode) { this.classNode = classNode; }

    public String getClassName() { return className; }
    public void setClassName(String className) { this.className = className; }

    public boolean isInterface() { return isInterface; }
    public void setInterface(boolean isInterface) { this.isInterface = isInterface; }

    public boolean isEnum() { return isEnum; }
    public void setEnum(boolean isEnum) { this.isEnum = isEnum; }

    public boolean isAbstract() { return isAbstract; }
    public void setAbstract(boolean isAbstract) { this.isAbstract = isAbstract; }

    public boolean isFinalClass() { return isFinalClass; }
    public void setFinalClass(boolean isFinalClass) { this.isFinalClass = isFinalClass; }

    public boolean hasInterfaces() { return hasInterfaces; }
    public void setHasInterfaces(boolean hasInterfaces) { this.hasInterfaces = hasInterfaces; }

    public List<String> getModifiers() { return modifiers; }
    public void setModifiers(List<String> modifiers) { this.modifiers = modifiers; }

    public String getClassBasePath() { return classBasePath; }
    public void setClassBasePath(String classBasePath) { this.classBasePath = classBasePath; }

    public String getClassHttpMethod() { return classHttpMethod; }
    public void setClassHttpMethod(String classHttpMethod) { this.classHttpMethod = classHttpMethod; }

    public String getSpringBeanType() { return springBeanType; }
    public void setSpringBeanType(String springBeanType) { this.springBeanType = springBeanType; }

    public String getSpringBeanName() { return springBeanName; }
    public void setSpringBeanName(String springBeanName) { this.springBeanName = springBeanName; }

    public String getSpringScope() { return springScope; }
    public void setSpringScope(String springScope) { this.springScope = springScope; }

    public boolean isPrimary() { return isPrimary; }
    public void setPrimary(boolean isPrimary) { this.isPrimary = isPrimary; }

    public boolean isLazy() { return isLazy; }
    public void setLazy(boolean isLazy) { this.isLazy = isLazy; }

    public boolean isMyBatisMapper() { return isMyBatisMapper; }
    public void setMyBatisMapper(boolean isMyBatisMapper) { this.isMyBatisMapper = isMyBatisMapper; }

    public boolean isMapStructMapper() { return isMapStructMapper; }
    public void setMapStructMapper(boolean isMapStructMapper) { this.isMapStructMapper = isMapStructMapper; }

    public String getMybatisDetectionMethod() { return mybatisDetectionMethod; }
    public void setMybatisDetectionMethod(String method) { this.mybatisDetectionMethod = method; }

    public String getMybatisMapperType() { return mybatisMapperType; }
    public void setMybatisMapperType(String type) { this.mybatisMapperType = type; }

    public String getMybatisMappingSource() { return mybatisMappingSource; }
    public void setMybatisMappingSource(String source) { this.mybatisMappingSource = source; }

    public String getConfigPropertiesPrefix() { return configPropertiesPrefix; }
    public void setConfigPropertiesPrefix(String prefix) { this.configPropertiesPrefix = prefix; }

    public boolean isAspect() { return isAspect; }
    public void setAspect(boolean isAspect) { this.isAspect = isAspect; }

    public boolean isClassAsync() { return isClassAsync; }
    public void setClassAsync(boolean isClassAsync) { this.isClassAsync = isClassAsync; }

    public String getClassAsyncExecutor() { return classAsyncExecutor; }
    public void setClassAsyncExecutor(String executor) { this.classAsyncExecutor = executor; }

    public boolean isNeedsProxy() { return needsProxy; }
    public void setNeedsProxy(boolean needsProxy) { this.needsProxy = needsProxy; }

    public String getProxyType() { return proxyType; }
    public void setProxyType(String proxyType) { this.proxyType = proxyType; }

    public boolean isQuartzJob() { return isQuartzJob; }
    public void setQuartzJob(boolean isQuartzJob) { this.isQuartzJob = isQuartzJob; }

    public boolean isExtendsQuartzJobBean() { return extendsQuartzJobBean; }
    public void setExtendsQuartzJobBean(boolean extendsQuartzJobBean) { this.extendsQuartzJobBean = extendsQuartzJobBean; }
}