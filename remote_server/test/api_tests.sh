#!/bin/bash

# AgentMessage Remote API Test Script
# This script tests all API endpoints of the AgentMessage remote database service

set -e  # Exit on any error

# Configuration
API_BASE_URL="https://battalions.cloud:8443"
TEST_DID="did:test:$(date +%s)"  # Unique DID for testing
TEST_DID_2="did:test:$(date +%s)_2"  # Second test DID

# SSL Configuration
CURL_SSL_OPTS="--insecure"  # Use --insecure for self-signed certificates, remove for production

echo "=== AgentMessage Remote API Test Suite ==="
echo "API Base URL: $API_BASE_URL"
echo "Test DID: $TEST_DID"
echo "Test DID 2: $TEST_DID_2"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print test results
print_test_result() {
    local test_name="$1"
    local status_code="$2"
    local expected_code="$3"
    
    if [ "$status_code" -eq "$expected_code" ]; then
        echo -e "${GREEN}✓ PASS${NC} - $test_name (HTTP $status_code)"
    else
        echo -e "${RED}✗ FAIL${NC} - $test_name (Expected HTTP $expected_code, got $status_code)"
    fi
}

# Function to make API request and return status code
api_request() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local expected_code="$4"
    local test_name="$5"
    
    echo -e "${BLUE}Testing:${NC} $test_name"
    echo "Request: $method $API_BASE_URL$endpoint"
    
    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" $CURL_SSL_OPTS -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" $CURL_SSL_OPTS -X "$method" "$API_BASE_URL$endpoint")
    fi
    
    # Split response and status code
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    echo "Response Body: $body"
    print_test_result "$test_name" "$status_code" "$expected_code"
    echo ""
    
    return $status_code
}

echo "=== 1. Health Check Test ==="
api_request "GET" "/health" "" "200" "Health Check"

echo "=== 2. List Identities (Empty) Test ==="
api_request "GET" "/identities" "" "200" "List Empty Identities"

echo "=== 3. Create Identity Test ==="
test_identity_1='{
    "did": "'$TEST_DID'",
    "name": "Test Agent 1",
    "description": "A test agent for API testing",
    "capabilities": ["chat", "code", "search"]
}'
api_request "POST" "/identities" "$test_identity_1" "201" "Create First Identity"

echo "=== 4. Create Second Identity Test ==="
test_identity_2='{
    "did": "'$TEST_DID_2'",
    "name": "Test Agent 2",
    "description": "Another test agent for API testing",
    "capabilities": ["analysis", "translation", "summarization"]
}'
api_request "POST" "/identities" "$test_identity_2" "201" "Create Second Identity"

echo "=== 5. List Identities (With Data) Test ==="
api_request "GET" "/identities" "" "200" "List Identities with Data"

echo "=== 6. Get Specific Identity Test ==="
api_request "GET" "/identities/$TEST_DID" "" "200" "Get First Identity by DID"

echo "=== 7. Get Non-existent Identity Test ==="
api_request "GET" "/identities/did:test:nonexistent" "" "404" "Get Non-existent Identity"

echo "=== 8. Update Identity Test ==="
updated_identity='{
    "did": "'$TEST_DID'",
    "name": "Updated Test Agent 1",
    "description": "An updated test agent for API testing",
    "capabilities": ["chat", "code", "search", "debugging"]
}'
api_request "PUT" "/identities/$TEST_DID" "$updated_identity" "200" "Update Identity"

echo "=== 9. Verify Update Test ==="
api_request "GET" "/identities/$TEST_DID" "" "200" "Verify Identity Update"

echo "=== 10. List with Pagination Test ==="
api_request "GET" "/identities?limit=1&offset=0" "" "200" "List with Pagination (limit=1, offset=0)"

echo "=== 11. Delete Identity Test ==="
api_request "DELETE" "/identities/$TEST_DID_2" "" "200" "Delete Second Identity"

echo "=== 12. Verify Deletion Test ==="
api_request "GET" "/identities/$TEST_DID_2" "" "404" "Verify Identity Deletion"

echo "=== 13. Final List Test ==="
api_request "GET" "/identities" "" "200" "Final Identity List"

echo "=== 14. Error Handling Tests ==="

echo "=== 14.1. Invalid JSON Test ==="
api_request "POST" "/identities" '{invalid json}' "400" "Invalid JSON"

echo "=== 14.2. Missing Required Fields Test ==="
incomplete_identity='{
    "name": "Incomplete Agent",
    "description": "Missing DID and capabilities"
}'
api_request "POST" "/identities" "$incomplete_identity" "400" "Missing Required Fields"

echo "=== 15. Cleanup Test ==="
api_request "DELETE" "/identities/$TEST_DID" "" "200" "Cleanup - Delete First Identity"

echo "=== Test Suite Complete ==="
echo -e "${GREEN}All tests completed!${NC}"
echo ""
echo "=== Additional Manual Tests ==="
echo "You can also test the following manually:"
echo ""
echo "1. PgAdmin Web Interface:"
echo "   URL: https://battalions.cloud:9128"
echo "   Email: admin@example.com"
echo "   Password: admin_password"
echo ""
echo "2. Direct PostgreSQL Connection:"
echo "   psql -h battalions.cloud -p 5432 -U agentmessage_user -d agentmessage"
echo ""
echo "3. Redis Connection:"
echo "   redis-cli -h battalions.cloud -p 6379"
echo ""
echo "4. Check all services status:"
echo "   curl --insecure https://battalions.cloud:8443/health"
echo "   nc -zv battalions.cloud 5432 6379 8443 9128"
echo ""
echo "5. SSL Certificate Information:"
echo "   openssl s_client -connect battalions.cloud:8443 -servername battalions.cloud"