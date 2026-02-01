package com.webank.asmanalysis.service;

import com.webank.asmanalysis.asm.ClassAnalyzer;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

/**
 * Service layer for ASM bytecode analysis.
 * Contains business logic migrated from the original ASMAnalysisService.
 */
@Service
public class AnalysisService {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisService.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    // ================================
    // 线程池配置（阶段 1：并发解析优化）
    // ================================
    @Value("${analysis.thread-pool.size:8}")
    private int threadPoolSize;

    @Value("${analysis.batch.size:1000}")
    private int analysisBatchSize;

    @Value("${asm.allowed.directories:}")
    private String allowedDirectoriesConfig;

    // 缓存解析后的允许目录列表
    private List<Path> allowedDirectories = null;

    // 性能监控指标
    private final AtomicInteger processedClasses = new AtomicInteger(0);
    private final AtomicInteger failedClasses = new AtomicInteger(0);

    /**
     * Analyze class files from given directories or files
     *
     * Request body (Option 1 - Package Roots):
     * {
     *   "packageRoots": ["/path/to/package1", "/path/to/package2"],
     *   "limit": 100  // optional
     * }
     *
     * Request body (Option 2 - Explicit Paths):
     * {
     *   "classDirs": ["/path/to/classes1", "/path/to/classes2"],
     *   "mapping": {
     *     "/path/to/classes1": "/path/to/sources1",
     *     "/path/to/classes2": "/path/to/sources2"
     *   },
     *   "limit": 100  // optional
     * }
     *
     * Request body (Option 3 - Individual Class Files):
     * {
     *   "classFiles": ["/path/to/MyClass.class", "/path/to/OtherClass.class"],
     *   "mapping": {
     *     "/path/to/classes": "/path/to/sources"
     *   },
     *   "domains": ["com.example.apps", "com.example"],  // optional: filter classes by FQN prefix
     *   "limit": 100  // optional
     * }
     */

    // ========== Parameter Parsing Methods ==========

    /**
     * 解析请求参数，提取文件路径和配置选项
     *
     * @param request 包含 packageRoots/classDirs/classFiles 的请求映射
     * @return 解析后的参数对象
     * @throws IllegalArgumentException 当缺少必需参数时
     */
    private ParsedResult parseRequest(Map<String, Object> request) {
        ParsedResult result = new ParsedResult();

        // 解析三种输入模式之一
        if (request.containsKey("packageRoots")) {
            processPackageRoots(request, result);
        } else if (request.containsKey("classDirs")) {
            processClassDirs(request, result);
        } else if (request.containsKey("classFiles")) {
            processClassFiles(request, result);
        } else {
            throw new IllegalArgumentException("Either packageRoots, classDirs, or classFiles is required");
        }

        // 解析可选参数
        parseOptionalParams(request, result);

        return result;
    }

    /**
     * 处理 packageRoots 模式：自动发现 classes/ 和 sources/ 目录
     */
    private void processPackageRoots(Map<String, Object> request, ParsedResult result) {
        @SuppressWarnings("unchecked")
        List<String> packageRoots = (List<String>) request.get("packageRoots");

        for (String packageRoot : packageRoots) {
            Path rootPath = Paths.get(packageRoot);

            // 自动检测包名（从目录名提取）
            if (result.getAutoDetectedPackageName() == null) {
                result.setAutoDetectedPackageName(rootPath.getFileName().toString());
            }

            Path classesPath = rootPath.resolve("classes");
            Path sourcesPath = rootPath.resolve("sources");

            if (Files.exists(classesPath) && Files.isDirectory(classesPath)) {
                String normalizedPath = normalizePath(classesPath.toString());
                result.addClassDir(normalizedPath);

                if (Files.exists(sourcesPath) && Files.isDirectory(sourcesPath)) {
                    result.addMapping(normalizedPath, normalizePath(sourcesPath.toString()));
                }
            } else {
                logger.warn("Warning: classes/ not found in {}", packageRoot);
            }
        }
    }

    /**
     * 处理 classDirs 模式：显式指定类目录
     */
    private void processClassDirs(Map<String, Object> request, ParsedResult result) {
        @SuppressWarnings("unchecked")
        List<String> explicitClassDirs = (List<String>) request.get("classDirs");

        for (String dir : explicitClassDirs) {
            result.addClassDir(normalizePath(dir));
        }

        if (request.containsKey("mapping")) {
            parseMapping(request, result);
        }
    }

    /**
     * 处理 classFiles 模式：显式指定单个类文件
     */
    private void processClassFiles(Map<String, Object> request, ParsedResult result) {
        @SuppressWarnings("unchecked")
        List<String> explicitClassFiles = (List<String>) request.get("classFiles");

        for (String classFilePath : explicitClassFiles) {
            try {
                Path path = validateAndNormalizePath(classFilePath);
                if (Files.exists(path) && path.toString().endsWith(".class")) {
                    result.addClassFile(path);
                } else {
                    logger.warn("Warning: invalid class file: {}", path);
                }
            } catch (SecurityException e) {
                logger.warn("Skipping file due to security restriction: {}", classFilePath);
            }
        }

        if (request.containsKey("mapping")) {
            parseMapping(request, result);
        }
    }

    /**
     * 解析可选参数：limit、domains、packageName
     */
    private void parseOptionalParams(Map<String, Object> request, ParsedResult result) {
        // limit
        if (request.containsKey("limit")) {
            result.setLimit(((Number) request.get("limit")).intValue());
        }

        // domains
        if (request.containsKey("domains")) {
            @SuppressWarnings("unchecked")
            List<String> domainsList = (List<String>) request.get("domains");
            result.getDomains().addAll(domainsList);
        }

        // packageName (优先使用显式值，否则使用自动检测的值)
        String detectedPackage = result.getAutoDetectedPackageName();
        String explicitPackage = request.containsKey("packageName") ?
            (String) request.get("packageName") : null;
        result.setPackageName(explicitPackage != null ? explicitPackage : detectedPackage);
    }

    /**
     * 解析 mapping 参数（由 classDirs 和 classFiles 共用）
     */
    private void parseMapping(Map<String, Object> request, ParsedResult result) {
        @SuppressWarnings("unchecked")
        Map<String, String> explicitMapping = (Map<String, String>) request.get("mapping");

        for (Map.Entry<String, String> entry : explicitMapping.entrySet()) {
            result.addMapping(
                normalizePath(entry.getKey()),
                normalizePath(entry.getValue())
            );
        }
    }

    /**
     * 收集所有 .class 文件
     * 如果未提供文件列表，则从目录中收集；然后应用 limit 限制
     */
    private void collectClassFiles(ParsedResult params) throws IOException {
        // 如果未提供文件列表，则从目录中收集
        if (params.getClassFiles().isEmpty()) {
            if (params.getClassDirs().isEmpty()) {
                throw new IllegalArgumentException("No valid class directories or files found");
            }

            for (String dirPath : params.getClassDirs()) {
                Path dir = Paths.get(dirPath);
                if (Files.exists(dir) && Files.isDirectory(dir)) {
                    Files.walk(dir)
                        .parallel()  // 阶段 1：启用并行文件收集
                        .filter(p -> p.toString().endsWith(".class"))
                        .forEach(params::addClassFile);
                }
            }
        }

        // 应用 limit 限制（阶段 1：将 Collection 转换为 List 以支持 subList）
        if (params.getLimit() != null && params.getClassFiles().size() > params.getLimit()) {
            List<Path> limitedList = new ArrayList<>(params.getClassFiles()).subList(0, params.getLimit());
            params.setClassFiles(limitedList);
        }
    }

    /**
     * 分析执行结果（包含 nodes 和 edges）
     * 阶段 1：预分配容量 + 线程安全
     */
    private static class AnalysisResult {
        private final List<Map<String, Object>> nodes;
        private final List<Map<String, Object>> edges;

        // 阶段 1：预分配容量（假设平均每个类 10 个节点 + 20 个边）
        public AnalysisResult(int estimatedClassCount) {
            int estimatedNodes = estimatedClassCount * 10;
            int estimatedEdges = estimatedClassCount * 20;

            // 使用线程安全集合
            this.nodes = Collections.synchronizedList(new ArrayList<>(estimatedNodes));
            this.edges = Collections.synchronizedList(new ArrayList<>(estimatedEdges));
        }

        public List<Map<String, Object>> getNodes() {
            return nodes;
        }

        public List<Map<String, Object>> getEdges() {
            return edges;
        }

        // 阶段 1：线程安全的添加方法
        public synchronized void addNodes(List<Map<String, Object>> newNodes) {
            nodes.addAll(newNodes);
        }

        public synchronized void addEdges(List<Map<String, Object>> newEdges) {
            edges.addAll(newEdges);
        }

        // 阶段 1：性能监控方法
        public int getNodeCount() {
            return nodes.size();
        }

        public int getEdgeCount() {
            return edges.size();
        }
    }

    /**
     * 执行类文件分析
     * 阶段 1：使用 ForkJoinPool 并行处理 .class 文件
     */
    private AnalysisResult analyzeFiles(List<Path> classFiles) {
        long startTime = System.currentTimeMillis();

        // 阶段 1：确保线程池大小有效（用于测试环境）
        int actualThreadPoolSize = threadPoolSize;
        if (actualThreadPoolSize <= 0) {
            actualThreadPoolSize = Runtime.getRuntime().availableProcessors();
        }

        logger.info("[ANALYSIS_START] Analyzing {} class files with {} threads",
            classFiles.size(), actualThreadPoolSize);

        // 阶段 1：预分配容量
        AnalysisResult result = new AnalysisResult(classFiles.size());

        // 重置性能计数器
        processedClasses.set(0);
        failedClasses.set(0);

        // 阶段 1：使用 ForkJoinPool 并行处理
        ForkJoinPool customPool = new ForkJoinPool(actualThreadPoolSize);

        try {
            customPool.submit(() ->
                classFiles.parallelStream()
                    .forEach(classFile -> {
                        try {
                            // 创建分析器（每个线程独立实例）
                            ClassAnalyzer analyzer = new ClassAnalyzer(classFile);
                            analyzer.analyze();

                            // 同步添加结果（线程安全）
                            result.addNodes(analyzer.getNodes());
                            result.addEdges(analyzer.getEdges());

                            // 更新进度
                            int count = processedClasses.incrementAndGet();
                            if (count % 1000 == 0) {
                                logger.info("[ANALYSIS_PROGRESS] Processed {}/{} classes",
                                    count, classFiles.size());
                            }
                        } catch (Exception e) {
                            failedClasses.incrementAndGet();
                            logger.error("[ANALYSIS_ERROR] Failed to analyze {}: {}",
                                classFile, e.getMessage());
                            // 不中断整体流程，继续处理其他文件
                        }
                    })
            ).get();  // 等待所有任务完成

        } catch (InterruptedException e) {
            logger.error("[ANALYSIS_INTERRUPTED] Analysis was interrupted", e);
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            logger.error("[ANALYSIS_FAILED] Parallel analysis failed", e);
        } finally {
            customPool.shutdown();
        }

        long duration = System.currentTimeMillis() - startTime;
        logger.info("[ANALYSIS_COMPLETE] Analyzed {} classes in {}ms ({} failed)",
            processedClasses.get(), duration, failedClasses.get());
        logger.info("[ANALYSIS_THROUGHPUT] {} classes/sec",
            (processedClasses.get() * 1000.0) / duration);

        return result;
    }

    /**
     * 构建响应数据
     * 阶段 1：合并多次遍历 + 预分配容量
     */
    private Map<String, Map<String, Object>> buildResponse(AnalysisResult analysisResult, ParsedResult params) {
        // 阶段 1：预分配 HashMap 容量
        int estimatedClassCount = analysisResult.getNodeCount() / 10;
        Map<String, Map<String, Object>> classByFqn = new HashMap<>(estimatedClassCount);
        Map<String, Map<String, Object>> methodByFqn = new HashMap<>(analysisResult.getNodeCount());

        // Define fields to exclude from automatic copying
        Set<String> CLASS_EXCLUDED_FIELDS = new HashSet<>(Arrays.asList(
            "nodeType", "fqn",
            "methods", "fields", "inheritance", "constructorInjections"));

        Set<String> METHOD_EXCLUDED_FIELDS = new HashSet<>(Arrays.asList(
            "nodeType", "fqn",
            "arguments", "calls"));

        Set<String> EDGE_EXCLUDED_FIELDS = new HashSet<>(Arrays.asList(
            "edgeType", "fromFqn"));

        // 阶段 1：合并 Step 1 和 Step 2 - 单次遍历 nodes
        for (Map<String, Object> node : analysisResult.getNodes()) {
            String nodeType = (String) node.get("nodeType");
            String fqn = (String) node.get("fqn");

            if ("class".equals(nodeType) || "interface".equals(nodeType) || "enum".equals(nodeType)) {
                // 初始化类数据
                Map<String, Object> classData = new HashMap<>();
                classData.put("methods", new ArrayList<Map<String, Object>>());
                classData.put("fields", new ArrayList<Map<String, Object>>());
                classData.put("inheritance", new ArrayList<Map<String, Object>>());
                classData.put("constructorInjections", new ArrayList<Map<String, Object>>());
                classData.put("fqn", fqn);
                classData.put("nodeType", nodeType);

                // 复制其他字段
                for (Map.Entry<String, Object> entry : node.entrySet()) {
                    String key = entry.getKey();
                    if (!CLASS_EXCLUDED_FIELDS.contains(key)) {
                        classData.put(key, entry.getValue());
                    }
                }

                classByFqn.put(fqn, classData);

            } else if ("method".equals(nodeType)) {
                String methodFqn = fqn;

                // 提取类 FQN
                int paramStart = methodFqn.indexOf('(');
                if (paramStart == -1) {
                    logger.warn("[FQN_PARSE_ERROR] Skipping malformed method FQN (no '('): {}", methodFqn);
                    continue;
                }
                int methodSep = methodFqn.lastIndexOf('.', paramStart);
                if (methodSep == -1) {
                    logger.warn("[FQN_PARSE_ERROR] Skipping malformed method FQN (no '.'): {}", methodFqn);
                    continue;
                }
                String classFqn = methodFqn.substring(0, methodSep);

                Map<String, Object> classData = classByFqn.get(classFqn);
                if (classData != null) {
                    Map<String, Object> methodData = new HashMap<>();
                    methodData.put("arguments", new ArrayList<String>());
                    methodData.put("calls", new ArrayList<Map<String, Object>>());
                    methodData.put("fqn", methodFqn);

                    // 复制其他字段
                    for (Map.Entry<String, Object> entry : node.entrySet()) {
                        String key = entry.getKey();
                        if (!METHOD_EXCLUDED_FIELDS.contains(key)) {
                            methodData.put(key, entry.getValue());
                        }
                    }

                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> methods = (List<Map<String, Object>>) classData.get("methods");
                    methods.add(methodData);

                    methodByFqn.put(methodFqn, methodData);
                }
            }
        }

        // Step 3: 处理 edges（保持原逻辑）
        for (Map<String, Object> edge : analysisResult.getEdges()) {
            String edgeType = (String) edge.get("edgeType");

            if ("inheritance".equals(edgeType)) {
                String fromFqn = (String) edge.get("fromFqn");
                Map<String, Object> classData = classByFqn.get(fromFqn);
                if (classData != null) {
                    Map<String, Object> inhData = new HashMap<>();
                    inhData.put("fqn", edge.get("toFqn"));
                    inhData.put("kind", edge.get("kind"));

                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> inheritance = (List<Map<String, Object>>) classData.get("inheritance");
                    inheritance.add(inhData);
                }
            } else if ("call".equals(edgeType)) {
                String fromFqn = (String) edge.get("fromFqn");
                Map<String, Object> methodData = methodByFqn.get(fromFqn);
                if (methodData != null) {
                    Map<String, Object> callData = new HashMap<>();

                    for (Map.Entry<String, Object> entry : edge.entrySet()) {
                        if (!EDGE_EXCLUDED_FIELDS.contains(entry.getKey())) {
                            callData.put(entry.getKey(), entry.getValue());
                        }
                    }

                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> calls = (List<Map<String, Object>>) methodData.get("calls");
                    calls.add(callData);
                }
            } else if ("member_of".equals(edgeType)) {
                String kind = (String) edge.get("kind");
                String fromFqn = (String) edge.get("fromFqn");
                String toFqn = (String) edge.get("toFqn");

                if ("return".equals(kind)) {
                    Map<String, Object> methodData = methodByFqn.get(toFqn);
                    if (methodData != null) {
                        methodData.put("returnType", fromFqn);
                    }
                } else if ("argument".equals(kind)) {
                    Map<String, Object> methodData = methodByFqn.get(toFqn);
                    if (methodData != null) {
                        @SuppressWarnings("unchecked")
                        List<String> arguments = (List<String>) methodData.get("arguments");
                        arguments.add(fromFqn);
                    }
                } else if (kind != null && (kind.equals("class") || kind.startsWith("class:"))) {
                    Map<String, Object> classData = classByFqn.get(toFqn);
                    if (classData != null) {
                        Map<String, Object> fieldData = new HashMap<>();
                        fieldData.put("type", fromFqn);

                        if (kind.startsWith("class:")) {
                            String injectionType = kind.substring(6);
                            fieldData.put("injectionType", injectionType);

                            if (edge.containsKey("qualifier")) {
                                fieldData.put("qualifier", edge.get("qualifier"));
                            }
                        }

                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> fields = (List<Map<String, Object>>) classData.get("fields");
                        fields.add(fieldData);
                    }
                } else if (kind != null && kind.startsWith("constructor:")) {
                    Map<String, Object> classData = classByFqn.get(toFqn);
                    if (classData != null) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> constructorInjections = (List<Map<String, Object>>) classData.get("constructorInjections");
                        if (constructorInjections == null) {
                            constructorInjections = new ArrayList<>();
                            classData.put("constructorInjections", constructorInjections);
                        }

                        Map<String, Object> injectionData = new HashMap<>();
                        injectionData.put("type", fromFqn);
                        injectionData.put("injectionType", kind.substring(12));

                        if (edge.containsKey("qualifier")) {
                            injectionData.put("qualifier", edge.get("qualifier"));
                        }

                        constructorInjections.add(injectionData);
                    }
                } else if (kind != null && kind.startsWith("setter:")) {
                    Map<String, Object> classData = classByFqn.get(toFqn);
                    if (classData != null) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> setterInjections = (List<Map<String, Object>>) classData.get("setterInjections");
                        if (setterInjections == null) {
                            setterInjections = new ArrayList<>();
                            classData.put("setterInjections", setterInjections);
                        }

                        Map<String, Object> injectionData = new HashMap<>();
                        injectionData.put("type", fromFqn);
                        injectionData.put("injectionType", kind.substring(7));

                        if (edge.containsKey("qualifier")) {
                            injectionData.put("qualifier", edge.get("qualifier"));
                        }

                        setterInjections.add(injectionData);
                    }
                }
            }
        }

        return classByFqn;
    }

    // ========== Main Analysis Method ==========

    public Map<String, Object> analyze(Map<String, Object> request) throws IOException {
        logger.info("[ANALYSIS_START] analyze method called with request keys: {}", request.keySet());

        // 解析请求参数
        ParsedResult params = parseRequest(request);

        // 收集所有 .class 文件并应用 limit 限制
        collectClassFiles(params);

        logger.info("Analyzing {} class files", params.getClassFiles().size());

        // 执行类文件分析（阶段 1：将 Collection 转换为 List）
        List<Path> classFilesList = new ArrayList<>(params.getClassFiles());
        AnalysisResult analysisResult = analyzeFiles(classFilesList);

        // 构建响应数据（重组为按类分组的结构）
        Map<String, Map<String, Object>> classByFqn = buildResponse(analysisResult, params);

        // Build final response
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("classes", new ArrayList<>(classByFqn.values()));
        logger.info("[ANALYSIS_COMPLETE] Analysis completed: {} classes processed, {} nodes, {} edges", classByFqn.size(), analysisResult.getNodes().size(), analysisResult.getEdges().size());

        return response;
    }

    /**
     * 流式分析端点（阶段 2：流式响应优化）
     *
     * @param request 请求参数（与 analyze 相同）
     * @param emitter SseEmitter 用于发送事件
     * @param batchSize 每批次返回的类数量
     * @throws IOException IO 异常
     */
    public void analyzeStream(Map<String, Object> request,
                             org.springframework.web.servlet.mvc.method.annotation.SseEmitter emitter,
                             int batchSize) throws IOException {
        logger.info("[STREAM_ANALYSIS_START] analyzeStream method called with batch size: {}", batchSize);

        // 解析请求参数
        ParsedResult params = parseRequest(request);

        // 收集所有 .class 文件并应用 limit 限制
        collectClassFiles(params);

        List<Path> classFilesList = new ArrayList<>(params.getClassFiles());
        int totalFiles = classFilesList.size();

        logger.info("[STREAM_ANALYSIS] Total class files: {}, batch size: {}", totalFiles, batchSize);

        // 分批处理
        int processedFiles = 0;
        int totalClasses = 0;
        int totalMethods = 0;
        int totalCalls = 0;

        while (processedFiles < totalFiles) {
            int endIndex = Math.min(processedFiles + batchSize, totalFiles);
            List<Path> batchFiles = classFilesList.subList(processedFiles, endIndex);

            logger.info("[STREAM_ANALYSIS] Processing batch {}/{} (files {}-{})",
                (processedFiles / batchSize) + 1, (totalFiles + batchSize - 1) / batchSize,
                processedFiles, endIndex);

            // 分析这批文件
            AnalysisResult batchResult = analyzeFiles(batchFiles);

            // 构建这批的响应
            Map<String, Map<String, Object>> classByFqn = buildResponse(batchResult, params);
            List<Map<String, Object>> batchClasses = new ArrayList<>(classByFqn.values());

            // 统计这批的数据
            int batchClassCount = batchClasses.size();
            int batchMethodCount = 0;
            long batchCallCount = 0;

            for (Map<String, Object> classData : batchClasses) {
                Object methodsObj = classData.getOrDefault("methods", Collections.emptyList());
                if (methodsObj instanceof List) {
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> methods = (List<Map<String, Object>>) methodsObj;
                    batchMethodCount += methods.size();

                    for (Map<String, Object> method : methods) {
                        Object callsObj = method.getOrDefault("calls", Collections.emptyList());
                        if (callsObj instanceof List) {
                            batchCallCount += ((List<?>) callsObj).size();
                        }
                    }
                }
            }

            totalClasses += batchClassCount;
            totalMethods += batchMethodCount;
            totalCalls += (int) batchCallCount;

            // 发送进度事件
            Map<String, Object> progressEvent = new HashMap<>();
            progressEvent.put("classes", batchClasses);
            progressEvent.put("progress", (endIndex * 100) / totalFiles);
            progressEvent.put("processed", endIndex);
            progressEvent.put("total", totalFiles);
            progressEvent.put("stats", Map.of(
                "totalClasses", totalClasses,
                "totalMethods", totalMethods,
                "totalCalls", totalCalls
            ));

            emitter.send(SseEmitter.event()
                .name("progress")
                .data(progressEvent));

            processedFiles = endIndex;
            logger.info("[STREAM_ANALYSIS] Batch completed: {} classes, {} methods, {} calls",
                batchClassCount, batchMethodCount, batchCallCount);
        }

        logger.info("[STREAM_ANALYSIS_COMPLETE] Stream analysis completed: {} classes, {} methods, {} calls",
            totalClasses, totalMethods, totalCalls);
    }

    /**
     * Lightweight indexing endpoint - returns grouped class symbols (excludes enums)
     *
     * Request body:
     * {
     *   "classFile": "/path/to/MyClass.class"
     * }
     */
    public Map<String, Object> index(Map<String, Object> request) throws IOException {
        // classFile is required
        if (!request.containsKey("classFile")) {
            throw new IllegalArgumentException("classFile is required");
        }

        String classFilePath = (String) request.get("classFile");

        // Validate class file
        Path classFile = Paths.get(classFilePath);
        if (!Files.exists(classFile) || !classFilePath.endsWith(".class")) {
            throw new IllegalArgumentException("Invalid class file: " + classFilePath);
        }

        logger.info("Indexing class file: {}", classFile);

        // Extract symbols
        String classFqn = null;
        boolean isEntity = false;
        List<Map<String, Object>> symbols = new ArrayList<>();

        try {
            ClassAnalyzer analyzer = new ClassAnalyzer(classFile);
            analyzer.analyze();

            // First pass: find the class node and check if it's an enum
            for (Map<String, Object> node : analyzer.getNodes()) {
                String nodeType = (String) node.get("nodeType");

                if ("enum".equals(nodeType)) {
                    // Skip enums entirely
                    Map<String, Object> response = new HashMap<>();
                    response.put("success", true);
                    response.put("skipped", true);
                    response.put("reason", "enum");
                    return response;
                }

                if ("class".equals(nodeType) || "interface".equals(nodeType)) {
                    classFqn = (String) node.get("fqn");
                    isEntity = node.get("isEntity") != null && (Boolean) node.get("isEntity");
                    break;
                }
            }

            // Second pass: collect all symbols (class + methods)
            for (Map<String, Object> node : analyzer.getNodes()) {
                String nodeType = (String) node.get("nodeType");
                String fqn = (String) node.get("fqn");

                Map<String, Object> symbol = new HashMap<>();
                symbol.put("fqn", fqn);
                symbol.put("nodeType", nodeType);
                symbol.put("line", node.get("lineNumber"));
                symbol.put("isEntity", isEntity); // Use class's isEntity for all symbols
                symbols.add(symbol);
            }
        } catch (Exception e) {
            throw new IOException("Failed to index " + classFile + ": " + e.getMessage(), e);
        }

        // Build grouped response
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("class_fqn", classFqn);
        response.put("is_entity", isEntity);
        response.put("symbols", symbols);

        return response;
    }

    /**
     * Batch indexing endpoint - indexes multiple class files in one request
     *
     * Request body:
     * {
     *   "classFiles": ["/path/to/Class1.class", "/path/to/Class2.class", ...]
     * }
     */
    public Map<String, Object> indexBatch(Map<String, Object> request) throws IOException {
        // classFiles is required
        if (!request.containsKey("classFiles")) {
            throw new IllegalArgumentException("classFiles array is required");
        }

        @SuppressWarnings("unchecked")
        List<String> classFilePaths = (List<String>) request.get("classFiles");

        if (classFilePaths == null || classFilePaths.isEmpty()) {
            throw new IllegalArgumentException("classFiles array cannot be empty");
        }

        logger.info("Batch indexing {} class files", classFilePaths.size());

        List<Map<String, Object>> results = new ArrayList<>();

        // Process each class file
        for (String classFilePath : classFilePaths) {
            Map<String, Object> result = new HashMap<>();

            try {
                // Validate class file
                Path classFile = Paths.get(classFilePath);
                if (!Files.exists(classFile) || !classFilePath.endsWith(".class")) {
                    result.put("success", false);
                    result.put("error", "Invalid class file: " + classFilePath);
                    results.add(result);
                    continue;
                }

                // Extract symbols
                String classFqn = null;
                boolean isEntity = false;
                boolean isEnum = false;
                List<Map<String, Object>> symbols = new ArrayList<>();

                ClassAnalyzer analyzer = new ClassAnalyzer(classFile);
                analyzer.analyze();

                // First pass: find the class node and check if it's an enum
                for (Map<String, Object> node : analyzer.getNodes()) {
                    String nodeType = (String) node.get("nodeType");

                    if ("enum".equals(nodeType)) {
                        // Skip enums entirely
                        isEnum = true;
                        break;
                    }

                    if ("class".equals(nodeType) || "interface".equals(nodeType)) {
                        classFqn = (String) node.get("fqn");
                        isEntity = node.get("isEntity") != null && (Boolean) node.get("isEntity");
                        break;
                    }
                }

                // If it's an enum, mark as skipped and continue to next file
                if (isEnum) {
                    result.put("success", true);
                    result.put("skipped", true);
                    result.put("reason", "enum");
                    results.add(result);
                    continue;
                }

                // Second pass: collect all symbols (class + methods)
                for (Map<String, Object> node : analyzer.getNodes()) {
                    String nodeType = (String) node.get("nodeType");
                    String fqn = (String) node.get("fqn");

                    Map<String, Object> symbol = new HashMap<>();
                    symbol.put("fqn", fqn);
                    symbol.put("nodeType", nodeType);
                    symbol.put("line", node.get("lineNumber"));
                    symbol.put("isEntity", isEntity);
                    symbols.add(symbol);
                }

                // Build result for this file
                result.put("success", true);
                result.put("class_fqn", classFqn);
                result.put("is_entity", isEntity);
                result.put("symbols", symbols);
                results.add(result);

            } catch (Exception e) {
                result.put("success", false);
                result.put("error", "Failed to index " + classFilePath + ": " + e.getMessage());
                results.add(result);
            }
        }

        // Build batch response
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("results", results);

        return response;
    }

    // ========== Parameter Parsing Helper Classes ==========

    /**
     * 解析后的请求参数容器
     *
     * 设计原则：
     * - 使用内部静态类保持封装性
     * - 提供便捷方法简化调用
     * - 包级私有访问权限
     */
    private static class ParsedResult {
        private List<String> classDirs = new ArrayList<>();
        // 阶段 1：使用线程安全集合支持并行文件收集
        private final Collection<Path> classFiles = new ConcurrentLinkedQueue<>();
        private Map<String, String> mapping = new HashMap<>();
        private Integer limit;
        private List<String> domains = new ArrayList<>();
        private String packageName;
        private String autoDetectedPackageName;

        // 便捷方法：添加单个元素
        void addClassDir(String dir) {
            if (dir != null && !dir.isEmpty()) {
                this.classDirs.add(dir);
            }
        }

        void addClassFile(Path file) {
            if (file != null) {
                this.classFiles.add(file);
            }
        }

        void addMapping(String key, String value) {
            if (key != null && value != null) {
                this.mapping.put(key, value);
            }
        }

        // Getters and Setters
        List<String> getClassDirs() { return classDirs; }
        Collection<Path> getClassFiles() { return classFiles; }
        Map<String, String> getMapping() { return mapping; }
        Integer getLimit() { return limit; }
        List<String> getDomains() { return domains; }
        String getPackageName() { return packageName; }
        String getAutoDetectedPackageName() { return autoDetectedPackageName; }

        void setClassDirs(List<String> classDirs) { this.classDirs = classDirs; }
        // 阶段 1：转换为 List 以支持 setClassFiles() 操作
        void setClassFiles(Collection<Path> classFiles) {
            this.classFiles.clear();
            this.classFiles.addAll(classFiles);
        }
        void setMapping(Map<String, String> mapping) { this.mapping = mapping; }
        void setLimit(Integer limit) { this.limit = limit; }
        void setDomains(List<String> domains) { this.domains = domains; }
        void setPackageName(String packageName) { this.packageName = packageName; }
        void setAutoDetectedPackageName(String name) { this.autoDetectedPackageName = name; }
    }

    /**
     * 规范化路径分隔符（跨平台兼容性）
     * 将 Windows 风格的反斜杠转换为 Unix 风格的正斜杠
     *
     * @param path 原始路径
     * @return 规范化后的路径
     */
    private String normalizePath(String path) {
        return path.replace('\\', '/');
    }

    /**
     * 验证路径是否在允许的目录列表中（防止路径遍历攻击）
     *
     * @param path 要验证的路径
     * @throws SecurityException 如果路径不在允许的目录中
     */
    private void validatePathSecurity(Path path) {
        // 如果没有配置允许目录，则允许所有路径（开发模式）
        if (allowedDirectoriesConfig == null || allowedDirectoriesConfig.trim().isEmpty()) {
            return;
        }

        // 延迟初始化允许目录列表
        if (allowedDirectories == null) {
            allowedDirectories = Arrays.stream(allowedDirectoriesConfig.split(","))
                    .map(String::trim)
                    .filter(s -> !s.isEmpty())
                    .map(Paths::get)
                    .map(Path::toAbsolutePath)
                    .map(Path::normalize)
                    .collect(Collectors.toList());
        }

        // 如果解析后为空，允许所有路径
        if (allowedDirectories.isEmpty()) {
            return;
        }

        // 规范化并验证路径
        Path normalizedPath = path.toAbsolutePath().normalize();

        // 检查是否在允许的目录中
        boolean isAllowed = allowedDirectories.stream()
                .anyMatch(allowedDir -> normalizedPath.startsWith(allowedDir));

        if (!isAllowed) {
            logger.warn("Path security violation: {} is not under allowed directories", normalizedPath);
            throw new SecurityException("Access denied: path is outside allowed directories");
        }
    }

    /**
     * 验证并规范化文件路径
     */
    private Path validateAndNormalizePath(String pathStr) {
        Path path = Paths.get(normalizePath(pathStr)).toAbsolutePath().normalize();
        validatePathSecurity(path);
        return path;
    }

    /**
     * Check if a class FQN matches any of the domain filters
     * Returns true if domains is empty OR if fqn starts with at least one domain
     */
    private boolean matchesDomainFilter(String fqn, List<String> domains) {
        if (domains == null || domains.isEmpty()) {
            return true;
        }
        for (String domain : domains) {
            if (fqn.startsWith(domain)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Health check response
     */
    public Map<String, Object> health() {
        Map<String, Object> health = new HashMap<>();
        health.put("status", "ok");
        health.put("service", "ASMAnalysisService (Spring Boot)");
        health.put("version", "1.0.0");
        health.put("timestamp", new Date());
        return health;
    }
}