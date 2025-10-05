#!/bin/bash

# FxCRUDView Integration Test Script
# Tests all CRUD operations against the experimental endpoint

set -e

# Configuration
BASE_URL="http://localhost:8000/experimental/courses"
CONTENT_TYPE="Content-Type: application/json"
FX_DATA="FX-Data: json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Helper functions
print_test() {
    echo -e "\n${YELLOW}Test $1:${NC} $2"
}

print_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC} - $1"
    ((FAILED++))
}

check_json_field() {
    local response="$1"
    local field="$2"
    if echo "$response" | jq -e "$field" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if server is running
echo "=== FxCRUDView Integration Tests ==="
echo "Testing against: $BASE_URL"
echo ""

if ! curl -s "$BASE_URL/" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Server not running at $BASE_URL${NC}"
    echo "Start server with: cd /Users/williamtalcott/projects/transcripts && python manage.py runserver"
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"

# Test 1: GET List (JSON)
print_test "1" "GET list with JSON response"
RESPONSE=$(curl -s "$BASE_URL/" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".data" && check_json_field "$RESPONSE" ".pagination"; then
    print_pass
else
    print_fail "Response missing required fields"
    echo "$RESPONSE" | jq . || echo "$RESPONSE"
fi

# Test 2: GET List (HTML)
print_test "2" "GET list with HTML response"
RESPONSE=$(curl -s "$BASE_URL/" -H "Accept: text/html")

if echo "$RESPONSE" | grep -q "<"; then
    print_pass
else
    print_fail "Expected HTML response"
fi

# Test 3: Search
print_test "3" "Search courses"
RESPONSE=$(curl -s "$BASE_URL/?q=Math" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".data"; then
    print_pass
else
    print_fail "Search failed"
    echo "$RESPONSE" | jq .
fi

# Test 4: Sort Ascending
print_test "4" "Sort by credits (ascending)"
RESPONSE=$(curl -s "$BASE_URL/?sort=credits&dir=asc" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".pagination"; then
    print_pass
else
    print_fail "Sort failed"
fi

# Test 5: Sort Descending
print_test "5" "Sort by completion_date (descending)"
RESPONSE=$(curl -s "$BASE_URL/?sort=completion_date&dir=desc" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".data"; then
    print_pass
else
    print_fail "Sort descending failed"
fi

# Test 6: Pagination
print_test "6" "Pagination (page 1, limit 5)"
RESPONSE=$(curl -s "$BASE_URL/?page=1&limit=5" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".pagination.page" && check_json_field "$RESPONSE" ".pagination.limit"; then
    PAGE=$(echo "$RESPONSE" | jq -r '.pagination.page')
    LIMIT=$(echo "$RESPONSE" | jq -r '.pagination.limit')
    if [ "$PAGE" = "1" ] && [ "$LIMIT" = "5" ]; then
        print_pass
    else
        print_fail "Pagination metadata incorrect"
    fi
else
    print_fail "Pagination failed"
fi

# Test 7: Column Configuration
print_test "7" "Column configuration"
RESPONSE=$(curl -s "$BASE_URL/" -H "$FX_DATA")

if check_json_field "$RESPONSE" ".columns"; then
    COLUMNS=$(echo "$RESPONSE" | jq -r '.columns | length')
    if [ "$COLUMNS" -gt 0 ]; then
        print_pass
    else
        print_fail "No columns returned"
    fi
else
    print_fail "Missing columns configuration"
fi

# Test 8: Create Course
print_test "8" "Create new course"
CREATE_DATA='{
  "student": 1,
  "class_title": "Integration Test Course",
  "subject": "Math",
  "completion_date": "2024-06-15",
  "credits": 1.0,
  "grade": "A",
  "course_type": "Standard"
}'

RESPONSE=$(curl -s -X POST "$BASE_URL/" \
    -H "$CONTENT_TYPE" \
    -H "$FX_DATA" \
    -d "$CREATE_DATA")

if check_json_field "$RESPONSE" ".success" && [ "$(echo "$RESPONSE" | jq -r '.success')" = "true" ]; then
    COURSE_ID=$(echo "$RESPONSE" | jq -r '.data.id')
    print_pass
    echo "  Created course ID: $COURSE_ID"
else
    print_fail "Create failed"
    echo "$RESPONSE" | jq .
    COURSE_ID=""
fi

# Test 9: Retrieve Single Course
if [ -n "$COURSE_ID" ]; then
    print_test "9" "Retrieve single course"
    RESPONSE=$(curl -s "$BASE_URL/$COURSE_ID/" -H "$FX_DATA")
    
    if check_json_field "$RESPONSE" ".id"; then
        TITLE=$(echo "$RESPONSE" | jq -r '.class_title // .title // empty')
        if [ "$TITLE" = "Integration Test Course" ]; then
            print_pass
        else
            print_fail "Course data mismatch"
        fi
    else
        print_fail "Retrieve failed"
    fi
else
    print_test "9" "Retrieve single course"
    print_fail "Skipped - no course ID from create"
fi

# Test 10: Inline Edit (single field)
if [ -n "$COURSE_ID" ]; then
    print_test "10" "Inline edit (update grade)"
    EDIT_DATA="{
      \"id\": $COURSE_ID,
      \"column\": \"grade\",
      \"value\": \"A+\"
    }"
    
    RESPONSE=$(curl -s -X PATCH "$BASE_URL/$COURSE_ID/" \
        -H "$CONTENT_TYPE" \
        -H "$FX_DATA" \
        -d "$EDIT_DATA")
    
    if check_json_field "$RESPONSE" ".success" && [ "$(echo "$RESPONSE" | jq -r '.success')" = "true" ]; then
        print_pass
    else
        print_fail "Inline edit failed"
        echo "$RESPONSE" | jq .
    fi
else
    print_test "10" "Inline edit"
    print_fail "Skipped - no course ID"
fi

# Test 11: Delete Course
if [ -n "$COURSE_ID" ]; then
    print_test "11" "Delete course"
    DELETE_DATA="{\"id\": $COURSE_ID}"
    
    RESPONSE=$(curl -s -X DELETE "$BASE_URL/$COURSE_ID/" \
        -H "$CONTENT_TYPE" \
        -H "$FX_DATA" \
        -d "$DELETE_DATA")
    
    if check_json_field "$RESPONSE" ".success" && [ "$(echo "$RESPONSE" | jq -r '.success')" = "true" ]; then
        print_pass
    else
        print_fail "Delete failed"
        echo "$RESPONSE" | jq .
    fi
else
    print_test "11" "Delete course"
    print_fail "Skipped - no course ID"
fi

# Summary
echo ""
echo "================================"
echo "Test Summary"
echo "================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total:  $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
