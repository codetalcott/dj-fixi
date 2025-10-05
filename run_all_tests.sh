#!/bin/bash

# Master Test Runner for dj-fixi and transcript demo
# Executes all validation steps in sequence

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
DJ_FIXI_DIR="/Users/williamtalcott/projects/dj-fixi"
TRANSCRIPT_DIR="/Users/williamtalcott/projects/transcripts"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  dj-fixi + FxCRUDView Validation Test Suite${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Step 0: Check prerequisites
echo -e "${YELLOW}Step 0: Checking prerequisites...${NC}"

if ! command -v uv &> /dev/null; then
    echo -e "${RED}✗ uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠ jq not found. Some tests may fail. Install with: apt install jq${NC}"
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Step 1: Setup dj-fixi environment
echo -e "${YELLOW}Step 1: Setting up dj-fixi test environment...${NC}"
cd "$DJ_FIXI_DIR"

if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment with uv..."
    uv venv --python 3.12
fi

echo "  Installing dependencies..."
uv pip install -e ".[dev]" --quiet

echo -e "${GREEN}✓ Environment ready${NC}"
echo ""

# Step 2: Run unit tests
echo -e "${YELLOW}Step 2: Running unit tests...${NC}"
cd "$DJ_FIXI_DIR"

source .venv/bin/activate

echo "  Running pytest..."
if pytest tests/ -v --tb=short 2>&1 | tee test_output.txt; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Some unit tests failed. Check test_output.txt${NC}"
fi

# Code coverage
echo "  Generating coverage report..."
if pytest tests/ --cov=dj_fixi --cov-report=term-missing --cov-report=html --quiet; then
    echo -e "${GREEN}✓ Coverage report generated (see htmlcov/index.html)${NC}"
else
    echo -e "${YELLOW}⚠ Coverage report failed${NC}"
fi

echo ""

# Step 3: Check if transcript server is running
echo -e "${YELLOW}Step 3: Checking Django server...${NC}"

if curl -s "http://localhost:8000/" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Django server is running${NC}"
    SERVER_RUNNING=true
else
    echo -e "${YELLOW}⚠ Django server not running${NC}"
    echo "  To start server: cd $TRANSCRIPT_DIR && python manage.py runserver"
    echo "  Skipping integration tests..."
    SERVER_RUNNING=false
fi

echo ""

# Step 4: Run integration tests (if server running)
if [ "$SERVER_RUNNING" = true ]; then
    echo -e "${YELLOW}Step 4: Running integration tests...${NC}"
    cd "$DJ_FIXI_DIR"
    
    chmod +x tests/integration_test.sh
    
    if ./tests/integration_test.sh 2>&1 | tee integration_output.txt; then
        echo -e "${GREEN}✓ Integration tests passed${NC}"
    else
        echo -e "${RED}✗ Some integration tests failed. Check integration_output.txt${NC}"
    fi
else
    echo -e "${YELLOW}Step 4: Skipping integration tests (server not running)${NC}"
fi

echo ""

# Step 5: Generate test report
echo -e "${YELLOW}Step 5: Generating test report...${NC}"

cat > "$DJ_FIXI_DIR/test_report.txt" << EOF
═══════════════════════════════════════════════════
  dj-fixi Validation Test Report
  Generated: $(date)
═══════════════════════════════════════════════════

UNIT TESTS
----------
$(grep -E "passed|failed|error" "$DJ_FIXI_DIR/test_output.txt" 2>/dev/null || echo "No output available")

INTEGRATION TESTS
-----------------
$(grep -E "Passed:|Failed:" "$DJ_FIXI_DIR/integration_output.txt" 2>/dev/null || echo "Not run (server not available)")

COVERAGE
--------
$(coverage report 2>/dev/null | tail -5 || echo "Coverage data not available")

FILES CREATED
-------------
✓ /Users/williamtalcott/projects/transcripts/transcript_manager/views_crud.py
✓ /Users/williamtalcott/projects/transcripts/transcript_manager/urls.py (updated)
✓ /Users/williamtalcott/projects/dj-fixi/tests/test_fxcrudview.py
✓ /Users/williamtalcott/projects/dj-fixi/tests/integration_test.sh
✓ /Users/williamtalcott/projects/dj-fixi/MCP_TOOLS_TEST_GUIDE.md
✓ /Users/williamtalcott/projects/dj-fixi/TEST_RESULTS.md

NEXT STEPS
----------
1. Review test results in test_output.txt and integration_output.txt
2. Fix any failing tests
3. Test MCP tools manually (see MCP_TOOLS_TEST_GUIDE.md)
4. Update TEST_RESULTS.md with findings
5. Start Django server if not running:
   cd $TRANSCRIPT_DIR && python manage.py runserver

MANUAL MCP TESTING
------------------
With Django server running, test MCP tools via Claude chat:
- Navigate to /experimental/agent-test/
- Query courses database
- Extract table data
- Test form interactions

See MCP_TOOLS_TEST_GUIDE.md for detailed instructions.
EOF

echo -e "${GREEN}✓ Test report saved to test_report.txt${NC}"
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
cat "$DJ_FIXI_DIR/test_report.txt"
echo ""

if [ "$SERVER_RUNNING" = true ]; then
    echo -e "${GREEN}✓ All automated tests complete${NC}"
else
    echo -e "${YELLOW}⚠ Integration tests skipped (start Django server to run)${NC}"
fi

echo ""
echo "View detailed results:"
echo "  - Unit tests: $DJ_FIXI_DIR/test_output.txt"
echo "  - Integration: $DJ_FIXI_DIR/integration_output.txt"
echo "  - Coverage: $DJ_FIXI_DIR/htmlcov/index.html"
echo "  - Summary: $DJ_FIXI_DIR/test_report.txt"
echo ""
echo "Next: Test MCP tools manually using MCP_TOOLS_TEST_GUIDE.md"
