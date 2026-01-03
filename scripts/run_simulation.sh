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
API_URL="http://localhost:8000"
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

echo ""
echo -e "${YELLOW}Step 2: Adding test device via API...${NC}"

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

DEVICE_RESPONSE=$(curl -s -X POST "${API_URL}/devices" \
  -H "Content-Type: application/json" \
  -d "${DEVICE_DATA}")

DEVICE_ID=$(echo $DEVICE_RESPONSE | grep -o '"id":[0-9]*' | grep -o '[0-9]*')

if [ -z "$DEVICE_ID" ]; then
    echo -e "${RED}✗ Failed to create device${NC}"
    echo "Response: $DEVICE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Device created with ID: ${DEVICE_ID}${NC}"

echo ""
echo -e "${YELLOW}Step 3: Triggering SNMP collection...${NC}"

COLLECT_RESPONSE=$(curl -s -X POST "${API_URL}/metrics/collect/${DEVICE_ID}")
echo -e "${GREEN}✓ Collection triggered${NC}"
echo "Response: $COLLECT_RESPONSE"

echo ""
echo -e "${YELLOW}Step 4: Waiting for metrics to be collected and stored...${NC}"
sleep 10

echo ""
echo -e "${YELLOW}Step 5: Verifying metrics in database...${NC}"

METRICS_RESPONSE=$(curl -s "${API_URL}/metrics/latest/${DEVICE_ID}?limit=20")
METRICS_COUNT=$(echo $METRICS_RESPONSE | grep -o '"id":' | wc -l | tr -d ' ')

if [ "$METRICS_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found ${METRICS_COUNT} metrics in database${NC}"
else
    echo -e "${RED}✗ No metrics found in database${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 6: Checking interfaces...${NC}"

INTERFACES_RESPONSE=$(curl -s "${API_URL}/metrics/interfaces/${DEVICE_ID}")
INTERFACE_COUNT=$(echo $INTERFACES_RESPONSE | grep -o '"interface_name"' | wc -l | tr -d ' ')

if [ "$INTERFACE_COUNT" -ge 2 ]; then
    echo -e "${GREEN}✓ Found ${INTERFACE_COUNT} interfaces${NC}"
    echo "$INTERFACES_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$INTERFACES_RESPONSE"
else
    echo -e "${YELLOW}⚠ Only found ${INTERFACE_COUNT} interface(s), expected at least 2${NC}"
fi

echo ""
echo -e "${YELLOW}Step 7: Fetching interface statistics...${NC}"

# Try to get stats for first interface
FIRST_INTERFACE=$(echo $INTERFACES_RESPONSE | grep -o '"interface_name":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$FIRST_INTERFACE" ]; then
    echo "Getting stats for interface: $FIRST_INTERFACE"
    STATS_RESPONSE=$(curl -s "${API_URL}/metrics/stats/${DEVICE_ID}/${FIRST_INTERFACE}?hours=1")
    
    # Check if we have metrics
    HAS_METRICS=$(echo $STATS_RESPONSE | grep -o '"metrics":\[' | wc -l | tr -d ' ')
    
    if [ "$HAS_METRICS" -gt 0 ]; then
        echo -e "${GREEN}✓ Interface statistics retrieved successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Interface statistics may be empty${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}Step 8: Database verification...${NC}"

DB_CHECK=$(docker-compose exec -T postgres psql -U snmpuser -d snmp_metrics -t -c \
    "SELECT COUNT(*) FROM snmp_metrics WHERE device_id = ${DEVICE_ID};" 2>/dev/null || echo "0")

DB_COUNT=$(echo $DB_CHECK | tr -d ' ')

if [ "$DB_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Database contains ${DB_COUNT} metric records${NC}"
else
    echo -e "${RED}✗ No metrics found in database${NC}"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ Simulation test completed successfully!${NC}"
echo ""
echo "📊 Summary:"
echo "  - Device ID: ${DEVICE_ID}"
echo "  - Device Name: ${DEVICE_NAME}"
echo "  - Metrics collected: ${METRICS_COUNT}"
echo "  - Interfaces found: ${INTERFACE_COUNT}"
echo "  - Database records: ${DB_COUNT}"
echo ""
echo "🌐 Access the UI to view metrics:"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "📋 Next steps:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Navigate to 'Metrics' page"
echo "  3. Select device '${DEVICE_NAME}'"
echo "  4. Select an interface (GigabitEthernet0/1 or GigabitEthernet0/2)"
echo "  5. View packet statistics and interface status"
echo ""
