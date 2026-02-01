package com.webank.asmanalysis;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Spring Boot 3 application for ASM bytecode analysis.
 *
 * This service provides REST endpoints for analyzing Java bytecode using ASM.
 * It replaces the original Spark-based ASMAnalysisService with a Spring Boot implementation.
 *
 * Default port: 8766 (to maintain compatibility with existing clients)
 */
@SpringBootApplication
public class AsmAnalysisApplication {

    public static void main(String[] args) {
        SpringApplication.run(AsmAnalysisApplication.class, args);
    }
}