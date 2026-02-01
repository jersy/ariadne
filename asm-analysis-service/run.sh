#!/bin/bash

# ASM Analysis Service (Spring Boot) - Startup Script
# Usage: ./run.sh [port]

set -e

# Default port
PORT=${1:-8766}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== ASM Analysis Service (Spring Boot 3) ===${NC}"
echo "Starting service on port $PORT"

# Check if Java 17+ is available
JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | cut -d'.' -f1)
if [[ "$JAVA_VERSION" -lt 17 ]]; then
    echo -e "${RED}Error: Java 17 or higher is required (found Java $JAVA_VERSION)${NC}"
    exit 1
fi

# Check if Maven is installed
if ! command -v mvn &> /dev/null; then
    echo -e "${RED}Error: Maven is not installed or not in PATH${NC}"
    exit 1
fi

# Build if target JAR doesn't exist
if [ ! -f "target/asm-analysis-service-spring-1.0.0.jar" ]; then
    echo -e "${YELLOW}JAR not found, building project...${NC}"
    mvn clean package -DskipTests
fi

# Run the service
echo -e "${GREEN}Starting service...${NC}"
echo "Press Ctrl+C to stop"
echo ""

java -Xmx2g -Dserver.port=$PORT -jar target/asm-analysis-service-spring-1.0.0.jar

echo -e "${GREEN}Service stopped${NC}"