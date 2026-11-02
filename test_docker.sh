#!/bin/bash
# Test Docker build and run locally

set -e

echo "🐳 Testing Docker image for Road Roughness Platform..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ No .env file found${NC}"
    echo "Creating from template..."
    cp .env.docker.example .env
    echo -e "${RED}❌ Please edit .env with your GEE credentials first${NC}"
    echo "   nano .env"
    exit 1
fi

# Check if GEE credentials are set
if ! grep -q '"type":"service_account"' .env; then
    echo -e "${RED}❌ GEE_SERVICE_ACCOUNT_JSON not configured in .env${NC}"
    echo "Please edit .env and add your service account JSON"
    exit 1
fi

# Build the image
echo -e "${GREEN}Step 1: Building Docker image...${NC}"
docker build -t road-roughness:test .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 2: Running container...${NC}"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Container started${NC}"
else
    echo -e "${RED}❌ Failed to start container${NC}"
    exit 1
fi

# Wait for app to start
echo ""
echo -e "${YELLOW}Waiting for application to start (30s)...${NC}"
sleep 30

# Test the API
echo ""
echo -e "${GREEN}Step 3: Testing API endpoint...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/config)

if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ API is responding (HTTP 200)${NC}"
    echo ""
    echo -e "${GREEN}🎉 Success! Application is running${NC}"
    echo ""
    echo "Access the application at:"
    echo "  🌐 http://localhost:8000"
    echo ""
    echo "View logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "Stop the application:"
    echo "  docker-compose down"
else
    echo -e "${RED}❌ API not responding (HTTP $RESPONSE)${NC}"
    echo ""
    echo "Check logs:"
    echo "  docker-compose logs"
    docker-compose logs --tail=50
    exit 1
fi
