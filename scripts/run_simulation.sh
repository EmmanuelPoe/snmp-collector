#!/bin/bash
set -e

echo "🧪 SNMP Collector - Automated Simulation Test"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost/api"
DEVICE_NAME="Test-Simulator"
DEVICE_IP="snmp-simulator"

echo -e "${YELLOW}Step 1: Waiting for services to be ready...${NC}"
sleep 5

# Wait for backend
echo "Waiting for backend API..."
for i in {1..30}; do
    if curl -s "${API_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Backend failed to start${NC}"
        exit 1
    fi
    sleep 2
done

# Wait for SNMP simulator
echo "Waiting for SNMP simulator..."
sleep 3
echo -e "${GREEN}✓ SNMP simulator should be ready${NC}"

# Authenticate
echo "Logging in as admin..."
TOKEN=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@localhost&password=admin" | jq -r '.access_token')
if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo -e "${RED}✗ Failed to authenticate${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Authenticated${NC}"
AUTH="-H \"Authorization: Bearer ${TOKEN}\""

echo ""
echo -e "${YELLOW}Step 2: Adding/Fetching test device via API...${NC}"

DEVICE_DATA='{
  "name": "'"${DEVICE_NAME}"'",
  "ip_address": "'"${DEVICE_IP}"'",
  "snmp_version": "2c",
  "snmp_community": "public",
  "snmp_port": 161,
  "device_type": "router",
  "description": "Simulated test router for automated testing",
  "enabled": true
}'

# POST device and capture status code and body
FULL_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/devices" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${DEVICE_DATA}")

DEVICE_RESPONSE=$(echo "$FULL_RESPONSE" | sed '$d')
HTTP_STATUS=$(echo "$FULL_RESPONSE" | tail -n 1)

DEVICE_ID=""

if [ "$HTTP_STATUS" -eq 201 ]; then
    DEVICE_ID=$(echo "$DEVICE_RESPONSE" | jq -r '.id')
    echo -e "${GREEN}✓ Device created with ID: ${DEVICE_ID}${NC}"
elif [ "$HTTP_STATUS" -eq 409 ]; then
    echo -e "${YELLOW}Device already exists, fetching ID...${NC}"
    # Fetch device by name from the list
    DEVICE_ID=$(curl -s "${API_URL}/devices" -H "Authorization: Bearer ${TOKEN}" | jq -r '.[] | select(.name=="'"${DEVICE_NAME}"'") | .id' | head -n 1)
    
    if [ -n "$DEVICE_ID" ] && [ "$DEVICE_ID" != "null" ]; then
        echo -e "${GREEN}✓ Found existing device with ID: ${DEVICE_ID}${NC}"
    else
        echo -e "${RED}✗ Failed to find existing device named ${DEVICE_NAME}${NC}"
        echo "Devices list: $(curl -s ${API_URL}/devices -H "Authorization: Bearer ${TOKEN}")"
        exit 1
    fi
else
    echo -e "${RED}✗ Unexpected API response (Status: ${HTTP_STATUS})${NC}"
    echo "Response body: $DEVICE_RESPONSE"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3: Waiting for agent to poll the device (90s)...${NC}"
echo "The agent polls on a 60s interval — waiting for first collection cycle..."
sleep 90

echo ""
echo -e "${YELLOW}Step 5: Verifying metrics in API...${NC}"

# Query for if_mib metrics specifically
METRICS_RESPONSE=$(curl -s "${API_URL}/metrics?device_id=${DEVICE_ID}&module=if_mib&limit=20" -H "Authorization: Bearer ${TOKEN}")
METRICS_COUNT=$(echo "$METRICS_RESPONSE" | jq '. | length')

if [ "$METRICS_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found ${METRICS_COUNT} metrics via API unpivoting${NC}"
else
    echo -e "${RED}✗ No metrics returned by API for module if_mib${NC}"
    # try generic if migration didn't work for some reason?
    GENERIC_COUNT=$(curl -s "${API_URL}/metrics?device_id=${DEVICE_ID}&limit=1" -H "Authorization: Bearer ${TOKEN}" | jq '. | length')
    echo "Debug: Generic metrics count: $GENERIC_COUNT"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 6: Checking interface list via available metrics...${NC}"

AVAILABLE_RESPONSE=$(curl -s "${API_URL}/metrics/available/${DEVICE_ID}" -H "Authorization: Bearer ${TOKEN}")
INTERFACE_COUNT=$(echo "$AVAILABLE_RESPONSE" | jq '.modules.if_mib.interfaces | length')

if [ "$INTERFACE_COUNT" -ge 2 ]; then
    echo -e "${GREEN}✓ Found ${INTERFACE_COUNT} interfaces${NC}"
else
    echo -e "${RED}✗ Interface discovery failed (Found: ${INTERFACE_COUNT})${NC}"
    echo "Available response: $AVAILABLE_RESPONSE"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 7: Verifying unpivoted interface stats...${NC}"

FIRST_INTERFACE=$(echo "$AVAILABLE_RESPONSE" | jq -r '.modules.if_mib.interfaces[0]')

if [ -n "$FIRST_INTERFACE" ] && [ "$FIRST_INTERFACE" != "null" ]; then
    echo "Checking stats for: $FIRST_INTERFACE"
    INTERFACE_STATS=$(curl -s "${API_URL}/metrics?device_id=${DEVICE_ID}&module=if_mib&interface_name=${FIRST_INTERFACE}&limit=5" -H "Authorization: Bearer ${TOKEN}")
    
    SAMPLE_VAL=$(echo "$INTERFACE_STATS" | jq -r '.[0].value')
    SAMPLE_NAME=$(echo "$INTERFACE_STATS" | jq -r '.[0].oid_name')
    
    if [ "$SAMPLE_VAL" != "null" ]; then
        echo -e "${GREEN}✓ Verified live data: ${SAMPLE_NAME} = ${SAMPLE_VAL}${NC}"
    else
        echo -e "${RED}✗ Failed to retrieve values for interface ${FIRST_INTERFACE}${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}Step 8: Total row count via metrics API...${NC}"

TOTAL_COUNT=$(curl -s "${API_URL}/metrics?device_id=${DEVICE_ID}&limit=10000" \
  -H "Authorization: Bearer ${TOKEN}" | jq '. | length')

echo "Total snmp_polls rows for device ${DEVICE_ID}: ${TOTAL_COUNT}"

if [ "$TOTAL_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Data confirmed in DuckDB via API (${TOTAL_COUNT} rows)${NC}"
else
    echo -e "${RED}✗ No rows returned via API for device ${DEVICE_ID}!${NC}"
    exit 1
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ Simulation test completed successfully!${NC}"
echo ""
echo "📊 Summary:"
echo "  - Device ID: ${DEVICE_ID}"
echo "  - Module: if_mib"
echo "  - Backend Type: Wide Table (if_mib_metrics)"
echo "  - API Status: Unpivoting working"
echo ""
echo "🌐 Access the UI:"
echo "  Frontend: http://localhost"
echo ""
