@echo off
REM ASM Analysis Service (Spring Boot) - Startup Script for Windows
REM Usage: run.bat [port]

setlocal enabledelayedexpansion

REM Default port
set PORT=8766
if not "%1"=="" set PORT=%1

echo === ASM Analysis Service (Spring Boot 3) ===
echo Starting service on port %PORT%

REM Check if Java 17+ is available
for /f "tokens=3" %%g in ('java -version 2^>^&1 ^| findstr /i "version"') do (
    set JAVAVER=%%g
    goto :checkjava
)
:checkjava
set JAVAVER=%JAVAVER:"=%
for /f "tokens=1,2 delims=." %%a in ("%JAVAVER%") do (
    set MAJOR=%%a
    goto :checkversion
)
:checkversion
if %MAJOR% LSS 17 (
    echo Error: Java 17 or higher is required (found Java %JAVAVER%)
    exit /b 1
)

REM Check if Maven is installed
where mvn >nul 2>nul
if errorlevel 1 (
    echo Error: Maven is not installed or not in PATH
    exit /b 1
)

REM Build if target JAR doesn't exist
if not exist "target\asm-analysis-service-spring-1.0.0.jar" (
    echo JAR not found, building project...
    call mvn clean package -DskipTests
)

REM Run the service
echo Starting service...
echo Press Ctrl+C to stop
echo.

java -Xmx2g -Dserver.port=%PORT% -jar target\asm-analysis-service-spring-1.0.0.jar

echo Service stopped