package com.webank.asmanalysis.controller;

import com.webank.asmanalysis.service.AnalysisService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.scheduling.annotation.Async;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * REST Controller for ASM bytecode analysis endpoints.
 * Provides the same API as the original ASMAnalysisService but implemented with Spring Boot.
 */
@RestController
@RequestMapping("/")
public class AnalysisController {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisController.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    private final AnalysisService analysisService;
    private final ApplicationContext applicationContext;

    @Autowired
    public AnalysisController(AnalysisService analysisService, ApplicationContext applicationContext) {
        this.analysisService = analysisService;
        this.applicationContext = applicationContext;
    }

    /**
     * Health check endpoint
     * GET /health
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        try {
            Map<String, Object> health = analysisService.health();
            return ResponseEntity.ok(health);
        } catch (Exception e) {
            logger.error("Health check failed", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("error", "Health check failed", "details", e.getMessage()));
        }
    }

    /**
     * Main analysis endpoint
     * POST /analyze
     */
    @PostMapping("/analyze")
    public ResponseEntity<String> analyze(@RequestBody Map<String, Object> request) {
        try {
            Map<String, Object> result = analysisService.analyze(request);
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(mapper.writeValueAsString(result));
        } catch (IllegalArgumentException e) {
            logger.warn("Bad request to /analyze: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Bad request: " + e.getMessage()));
        } catch (IOException e) {
            logger.error("IO error during analysis", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Analysis failed: " + e.getMessage()));
        } catch (Exception e) {
            logger.error("Unexpected error during analysis", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Internal server error: " + e.getMessage()));
        }
    }

    /**
     * Streaming analysis endpoint (阶段 2：流式响应优化)
     * POST /analyze/stream
     *
     * 使用 Server-Sent Events (SSE) 分批返回结果，避免大 JSON 问题。
     *
     * 请求格式与 /analyze 相同：
     * {
     *   "classFiles": [...],
     *   "streamBatchSize": 1000  // 可选，每批返回的类数量（默认 1000）
     * }
     *
     * SSE 事件格式：
     * - event: start - 开始分析
     * - event: progress - 批次进度
     * - event: complete - 分析完成
     * - event: error - 错误
     */
    @PostMapping(value = "/analyze/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter analyzeStream(@RequestBody Map<String, Object> request) {
        // 创建超时时间为 10 分钟的 SseEmitter
        SseEmitter emitter = new SseEmitter(600000L);

        logger.info("[STREAM] Analysis request received");

        // 在异步线程中处理
        ExecutorService executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> {
            try {
                // 解析参数
                int streamBatchSize = 1000; // 默认每批 1000 个类
                if (request.containsKey("streamBatchSize")) {
                    streamBatchSize = ((Number) request.get("streamBatchSize")).intValue();
                }

                logger.info("[STREAM] Starting analysis with batch size: {}", streamBatchSize);

                // 发送开始事件
                Map<String, Object> startEvent = new HashMap<>();
                startEvent.put("message", "Starting analysis");
                startEvent.put("batchSize", streamBatchSize);
                emitter.send(SseEmitter.event()
                    .name("start")
                    .data(startEvent));

                // 调用分析服务的流式方法
                analysisService.analyzeStream(request, emitter, streamBatchSize);

                // 发送完成事件
                Map<String, Object> completeEvent = new HashMap<>();
                completeEvent.put("message", "Analysis completed");
                completeEvent.put("timestamp", System.currentTimeMillis());
                emitter.send(SseEmitter.event()
                    .name("complete")
                    .data(completeEvent));

                emitter.complete();
                logger.info("[STREAM] Analysis completed successfully");

            } catch (Exception e) {
                logger.error("[STREAM] Analysis failed", e);
                try {
                    Map<String, Object> errorEvent = new HashMap<>();
                    errorEvent.put("error", e.getMessage());
                    errorEvent.put("type", e.getClass().getSimpleName());
                    emitter.send(SseEmitter.event()
                        .name("error")
                        .data(errorEvent));
                    emitter.completeWithError(e);
                } catch (IOException ioException) {
                    logger.error("[STREAM] Failed to send error event", ioException);
                    emitter.completeWithError(ioException);
                }
            } finally {
                executor.shutdown();
            }
        });

        return emitter;
    }

    /**
     * Lightweight indexing endpoint (single file)
     * POST /index
     */
    @PostMapping("/index")
    public ResponseEntity<String> index(@RequestBody Map<String, Object> request) {
        try {
            Map<String, Object> result = analysisService.index(request);
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(mapper.writeValueAsString(result));
        } catch (IllegalArgumentException e) {
            logger.warn("Bad request to /index: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Bad request: " + e.getMessage()));
        } catch (IOException e) {
            logger.error("IO error during indexing", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Indexing failed: " + e.getMessage()));
        } catch (Exception e) {
            logger.error("Unexpected error during indexing", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Internal server error: " + e.getMessage()));
        }
    }

    /**
     * Batch indexing endpoint
     * POST /index/batch
     */
    @PostMapping("/index/batch")
    public ResponseEntity<String> indexBatch(@RequestBody Map<String, Object> request) {
        try {
            Map<String, Object> result = analysisService.indexBatch(request);
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(mapper.writeValueAsString(result));
        } catch (IllegalArgumentException e) {
            logger.warn("Bad request to /index/batch: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Bad request: " + e.getMessage()));
        } catch (IOException e) {
            logger.error("IO error during batch indexing", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Batch indexing failed: " + e.getMessage()));
        } catch (Exception e) {
            logger.error("Unexpected error during batch indexing", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(errorResponse("Internal server error: " + e.getMessage()));
        }
    }

    /**
     * Shutdown endpoint (for compatibility with original service)
     * POST /shutdown
     *
     * Note: In production, consider using Spring Boot Actuator's shutdown endpoint instead.
     */
    @PostMapping("/shutdown")
    public ResponseEntity<String> shutdown() {
        logger.info("Shutdown request received, stopping service...");

        // Return response immediately
        Map<String, Object> response = new HashMap<>();
        response.put("status", "shutting down");
        response.put("message", "Service will stop shortly");

        // Shutdown in a separate thread to allow response to be sent
        new Thread(() -> {
            try {
                Thread.sleep(500); // Give time for response to be sent
                logger.info("Initiating application shutdown...");

                // Option 1: Exit the JVM (mimics original behavior)
                // System.exit(0);

                // Option 2: Graceful Spring shutdown (recommended)
                // This requires spring-boot-starter-actuator and management.endpoints.web.exposure.include=shutdown
                // For now, we'll use a simple exit to maintain compatibility
                // Check if we're in a test environment to avoid killing the test JVM
                // Use system property 'test.mode' set by Maven Surefire plugin
                boolean isTestEnvironment = "true".equals(System.getProperty("test.mode"));

                if (isTestEnvironment) {
                    logger.info("Shutdown requested but System.exit disabled in test mode (test.mode=true)");
                } else {
                    logger.info("Initiating JVM shutdown via System.exit(0)");
                    System.exit(0);
                }
            } catch (InterruptedException e) {
                logger.error("Error during shutdown", e);
                Thread.currentThread().interrupt();
            }
        }).start();

        try {
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(mapper.writeValueAsString(response));
        } catch (JsonProcessingException e) {
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"status\": \"shutting down\"}");
        }
    }

    /**
     * Handle JSON parsing errors (invalid JSON format)
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<String> handleHttpMessageNotReadableException(HttpMessageNotReadableException e) {
        logger.warn("Invalid JSON request: {}", e.getMessage());
        return ResponseEntity.badRequest()
                .contentType(MediaType.APPLICATION_JSON)
                .body(errorResponse("Invalid JSON format: " + e.getMessage()));
    }

    /**
     * Global exception handler for this controller
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<String> handleException(Exception e) {
        logger.error("Unhandled exception in controller", e);

        Map<String, String> error = new HashMap<>();
        error.put("error", e.getMessage());
        error.put("type", e.getClass().getSimpleName());

        try {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(mapper.writeValueAsString(error));
        } catch (JsonProcessingException ex) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"error\": \"Internal server error\"}");
        }
    }

    /**
     * Helper method to create error response JSON
     */
    private String errorResponse(String message) {
        try {
            Map<String, String> error = new HashMap<>();
            error.put("error", message);
            return mapper.writeValueAsString(error);
        } catch (JsonProcessingException e) {
            return "{\"error\": \"Error generating error response\"}";
        }
    }
}