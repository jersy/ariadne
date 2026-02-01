package com.webank.asmanalysis.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.webank.asmanalysis.service.AnalysisService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.ApplicationContext;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.HashMap;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * 测试AnalysisController的所有REST端点
 */
@ExtendWith(MockitoExtension.class)
class AnalysisControllerTest {

    private MockMvc mockMvc;

    @Mock
    private AnalysisService analysisService;

    @Mock
    private ApplicationContext applicationContext;

    @InjectMocks
    private AnalysisController analysisController;

    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(analysisController).build();
        objectMapper = new ObjectMapper();
    }

    @Test
    void testHealthEndpoint() throws Exception {
        // 准备模拟数据
        Map<String, Object> healthResponse = new HashMap<>();
        healthResponse.put("status", "healthy");
        healthResponse.put("version", "1.0.0");
        healthResponse.put("service", "ASM Analysis Service");

        when(analysisService.health()).thenReturn(healthResponse);

        // 执行测试
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("healthy"))
                .andExpect(jsonPath("$.version").value("1.0.0"))
                .andExpect(jsonPath("$.service").value("ASM Analysis Service"));
    }

    @Test
    void testAnalyzeEndpointSuccess() throws Exception {
        // 准备请求和响应
        Map<String, Object> request = new HashMap<>();
        request.put("classFiles", new String[]{"/path/to/Test.class"});
        request.put("enhanced", true);
        request.put("springAnalysis", true);

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("classes", new HashMap[]{});
        response.put("stats", Map.of("totalClasses", 1, "totalMethods", 10, "totalCalls", 5));

        when(analysisService.analyze(any(Map.class))).thenReturn(response);

        // 执行测试
        mockMvc.perform(post("/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.stats.totalClasses").value(1));
    }

    @Test
    void testAnalyzeEndpointBadRequest() throws Exception {
        // 模拟IllegalArgumentException
        when(analysisService.analyze(any(Map.class)))
                .thenThrow(new IllegalArgumentException("Missing required field: classFiles"));

        Map<String, Object> request = new HashMap<>();
        request.put("enhanced", true);

        mockMvc.perform(post("/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.error").value("Bad request: Missing required field: classFiles"));
    }

    @Test
    void testAnalyzeEndpointIOException() throws Exception {
        // 模拟IOException
        when(analysisService.analyze(any(Map.class)))
                .thenThrow(new java.io.IOException("File not found"));

        Map<String, Object> request = new HashMap<>();
        request.put("classFiles", new String[]{"/nonexistent/file.class"});

        mockMvc.perform(post("/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.error").value("Analysis failed: File not found"));
    }

    @Test
    void testIndexEndpointSuccess() throws Exception {
        // 准备请求和响应
        Map<String, Object> request = new HashMap<>();
        request.put("classFile", "/path/to/Test.class");

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("symbols", new HashMap[]{});

        when(analysisService.index(any(Map.class))).thenReturn(response);

        mockMvc.perform(post("/index")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void testIndexBatchEndpointSuccess() throws Exception {
        // 准备请求和响应
        Map<String, Object> request = new HashMap<>();
        request.put("classFiles", new String[]{"/path/to/Test1.class", "/path/to/Test2.class"});

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("totalSymbols", 50);

        when(analysisService.indexBatch(any(Map.class))).thenReturn(response);

        mockMvc.perform(post("/index/batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.totalSymbols").value(50));
    }

    @Test
    void testShutdownEndpoint() throws Exception {
        // shutdown端点应该返回200 OK
        mockMvc.perform(post("/shutdown"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("shutting down"))
                .andExpect(jsonPath("$.message").value("Service will stop shortly"));
    }

    @Test
    void testGlobalExceptionHandler() throws Exception {
        // 模拟未处理的异常
        when(analysisService.health())
                .thenThrow(new RuntimeException("Unexpected error"));

        mockMvc.perform(get("/health"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.error").value("Health check failed"))
                .andExpect(jsonPath("$.details").value("Unexpected error"));
    }

    @Test
    void testErrorResponseGeneration() throws Exception {
        // 测试错误响应生成
        Map<String, Object> request = new HashMap<>();
        // 空请求应该触发验证错误

        // 这里我们直接测试控制器的错误响应能力
        // 通过发送无效JSON来测试
        mockMvc.perform(post("/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{ invalid json }"))
                .andExpect(status().isBadRequest());
    }
}