# Validation Execution Checklist

Use this checklist to execute all validation steps.

---

## Pre-Flight Checklist

- [ ] **uv installed**: Run `uv --version`
- [ ] **jq installed** (optional): Run `jq --version`
- [ ] **Projects accessible**:
  - [ ] `/Users/williamtalcott/projects/dj-fixi`
  - [ ] `/Users/williamtalcott/projects/transcripts`

---

## Step 1: Automated Tests (10 minutes)

### 1.1 Run Master Test Script

```bash
cd /Users/williamtalcott/projects/dj-fixi
./run_all_tests.sh
```

- [ ] Script completed successfully
- [ ] Unit tests ran (check `test_output.txt`)
- [ ] Coverage report generated (check `htmlcov/index.html`)
- [ ] Integration tests attempted

### 1.2 Review Unit Test Results

```bash
cat test_output.txt
```

- [ ] Record number of tests: _____ passed, _____ failed
- [ ] Coverage percentage: _____%
- [ ] Note any failures:
  ```
  
  
  ```

### 1.3 Review Integration Results

```bash
cat integration_output.txt
```

- [ ] Integration tests ran (or note if skipped)
- [ ] Record results: _____ passed, _____ failed
- [ ] Note any failures:
  ```
  
  
  ```

---

## Step 2: Start Django Server (2 minutes)

### 2.1 Navigate to Transcript Project

```bash
cd /Users/williamtalcott/projects/transcripts
```

### 2.2 Start Development Server

```bash
python manage.py runserver
```

- [ ] Server started successfully
- [ ] Accessible at http://localhost:8000
- [ ] No migration errors

### 2.3 Verify Endpoints

Open browser or use curl:

```bash
# Test home page
curl -s http://localhost:8000/ | head -10

# Test experimental endpoint
curl -s http://localhost:8000/experimental/courses/ -H "FX-Data: json" | jq .
```

- [ ] Home page loads
- [ ] Experimental endpoint returns JSON
- [ ] No 500 errors

---

## Step 3: Test MCP Tools (15 minutes)

### 3.1 Prepare Test Environment

- [ ] Django server running (from Step 2)
- [ ] Claude Desktop open
- [ ] MCP server configured

### 3.2 Run MCP Tests

Open Claude chat and test each tool:

#### Test 1: Navigate
```
Navigate to /experimental/agent-test/ and describe what you see
```
- [ ] Successfully navigated
- [ ] Page content extracted
- [ ] Response time: _____ms

#### Test 2: Query Courses
```
Query the courses database and show me the first 5 courses
```
- [ ] Query successful
- [ ] Results returned
- [ ] Response time: _____ms
- [ ] Response format correct (success, data, meta)

#### Test 3: Query with Filter
```
Show me all courses where the subject is "Math"
```
- [ ] Filtering works
- [ ] Only Math courses returned
- [ ] Response time: _____ms

#### Test 4: Extract Data
```
Navigate to /experimental/courses/ and extract the page structure
```
- [ ] Data extracted successfully
- [ ] Structured format returned
- [ ] Response time: _____ms

#### Test 5: Get Table Data
```
Extract the course table data from /experimental/courses/
```
- [ ] Table parsed correctly
- [ ] Headers and rows returned
- [ ] Response time: _____ms

#### Test 6: Extract Action Elements
```
What interactive elements (buttons, forms) are on the page?
```
- [ ] Elements identified
- [ ] Selectors provided
- [ ] Response time: _____ms

---

## Step 4: Manual Integration Test (10 minutes)

### 4.1 Test Full CRUD Cycle via curl

#### CREATE
```bash
curl -X POST http://localhost:8000/experimental/courses/ \
  -H "Content-Type: application/json" \
  -H "FX-Data: json" \
  -d '{
    "student": 1,
    "class_title": "Manual Test Course",
    "subject": "Math",
    "completion_date": "2024-06-15",
    "credits": 1.0,
    "grade": "A"
  }' | jq .
```
- [ ] Created successfully
- [ ] Record course ID: _____
- [ ] Response time: _____ms

#### RETRIEVE
```bash
# Replace <ID> with course ID from create
curl http://localhost:8000/experimental/courses/<ID>/ \
  -H "FX-Data: json" | jq .
```
- [ ] Retrieved successfully
- [ ] Data matches created course
- [ ] Response time: _____ms

#### UPDATE (Inline)
```bash
curl -X PATCH http://localhost:8000/experimental/courses/<ID>/ \
  -H "Content-Type: application/json" \
  -H "FX-Data: json" \
  -d '{
    "id": <ID>,
    "column": "grade",
    "value": "A+"
  }' | jq .
```
- [ ] Updated successfully
- [ ] Grade changed to A+
- [ ] Response time: _____ms

#### DELETE
```bash
curl -X DELETE http://localhost:8000/experimental/courses/<ID>/ \
  -H "Content-Type: application/json" \
  -H "FX-Data: json" \
  -d '{"id": <ID>}' | jq .
```
- [ ] Deleted successfully
- [ ] Response time: _____ms

#### VERIFY DELETION
```bash
curl http://localhost:8000/experimental/courses/<ID>/ \
  -H "FX-Data: json"
```
- [ ] Returns 404 or error
- [ ] Course no longer exists

---

## Step 5: Document Results (10 minutes)

### 5.1 Update TEST_RESULTS.md

Open and update `/Users/williamtalcott/projects/dj-fixi/TEST_RESULTS.md`:

- [ ] Fill in Step 1 results (Unit tests)
- [ ] Fill in Step 2 implementation status
- [ ] Fill in Step 3 MCP tool results
- [ ] Fill in Step 4 integration test results
- [ ] Record performance metrics
- [ ] Document any issues found

### 5.2 Calculate Success Rates

**Unit Tests**:
- Pass rate: _____% (_____ / _____)

**Integration Tests**:
- Pass rate: _____% (_____ / _____)

**MCP Tools**:
- Success rate: _____% (_____ / 6)

**Overall**:
- Total tests: _____
- Total passed: _____
- Overall pass rate: _____%

---

## Step 6: Performance Analysis (5 minutes)

### 6.1 Measure Response Times

Record actual vs target response times:

| Operation | Target | Actual | Status |
|-----------|--------|--------|--------|
| List (100) | <500ms | ___ms | ⏳ |
| Retrieve | <100ms | ___ms | ⏳ |
| Create | <200ms | ___ms | ⏳ |
| Update | <150ms | ___ms | ⏳ |
| Delete | <100ms | ___ms | ⏳ |
| Search | <300ms | ___ms | ⏳ |
| MCP Tool | <100ms | ___ms | ⏳ |

### 6.2 Check Database Queries

Enable SQL logging and check query counts:

- [ ] List view: _____ queries
- [ ] Detail view: _____ queries
- [ ] N+1 issues: _____ (target: 0)

---

## Step 7: Issues & Fixes (as needed)

### 7.1 Document Issues

For each issue found:

**Issue #1**:
- Description: 
- Severity: High / Medium / Low
- Test: 
- Status: Open / Fixed

**Issue #2**:
- Description: 
- Severity: High / Medium / Low
- Test: 
- Status: Open / Fixed

### 7.2 Apply Fixes

- [ ] Fix high priority issues
- [ ] Re-run failed tests
- [ ] Verify fixes work

---

## Step 8: Final Validation (5 minutes)

### 8.1 Summary Check

- [ ] All unit tests passing (or documented failures)
- [ ] All integration tests passing (or documented failures)
- [ ] All MCP tools working
- [ ] Performance within targets
- [ ] No critical issues

### 8.2 Sign-Off

- [ ] TEST_RESULTS.md complete
- [ ] Issues documented
- [ ] Coverage >85% (or explained)
- [ ] Ready for production: Yes / No

**Validated by**: _________________
**Date**: _____________________
**Notes**:
```



```

---

## Quick Reference

### Key Files

- **Test Scripts**: `run_all_tests.sh`, `integration_test.sh`
- **Results**: `TEST_RESULTS.md`, `test_output.txt`, `integration_output.txt`
- **Coverage**: `htmlcov/index.html`
- **Guide**: `MCP_TOOLS_TEST_GUIDE.md`
- **Summary**: `EXEC_SUMMARY.md`

### Key Commands

```bash
# Run all tests
./run_all_tests.sh

# Run unit tests only
source .venv/bin/activate && pytest tests/ -v

# Run integration tests only
./tests/integration_test.sh

# Start Django server
cd /Users/williamtalcott/projects/transcripts && python manage.py runserver

# View coverage
open htmlcov/index.html
```

---

## Estimated Time

| Step | Time | Cumulative |
|------|------|------------|
| Pre-flight | 2 min | 2 min |
| Step 1 | 10 min | 12 min |
| Step 2 | 2 min | 14 min |
| Step 3 | 15 min | 29 min |
| Step 4 | 10 min | 39 min |
| Step 5 | 10 min | 49 min |
| Step 6 | 5 min | 54 min |
| Step 7 | Variable | - |
| Step 8 | 5 min | 59 min |
| **Total** | **~1 hour** | |

---

## Success!

When all steps are complete:
- ✅ 14 files created
- ✅ 2,100+ lines of code written
- ✅ 39 tests implemented
- ✅ Full validation infrastructure ready

You now have comprehensive validation for both **FixiPlug-Agent MCP Tools** and **FxCRUDView**!
