# Quick Guide: Running P3 Integration Tests

## Prerequisites

1. **Start the backend service:**
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

2. **Verify service is running:**
```bash
curl http://localhost:8000/healthz
```

## Quick Start

### Run All Active Tests (Skip External Dependencies)
```bash
pytest tests/e2e/test_e2e_integration.py -v -s
```

### Run with HTML Report
```bash
pytest tests/e2e/test_e2e_integration.py -v --html=report_p3.html --self-contained-html
```

## Run by Test Class

```bash
# Tag weight feedback (3 tests)
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback -v -s

# Sniffer to KB flow (3 tests - all skipped by default)
pytest tests/e2e/test_e2e_integration.py::TestSnifferToKBFlow -v -s

# Trending integration (4 tests - 1 skipped by default)
pytest tests/e2e/test_e2e_integration.py::TestTrendingIntegration -v -s

# Cross-system data flow (3 tests)
pytest tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow -v -s

# E2E workflows (2 tests - 1 skipped by default)
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows -v -s
```

## Run Specific Tests

```bash
# Tag weight increment test
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_kb_addition_increments_tag_weights -v -s

# Resource lifecycle test
pytest tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow::test_resource_lifecycle_across_systems -v -s

# Complete workflow test
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows::test_complete_user_workflow_source_to_kb -v -s
```

## Test Summary

### Active Tests (10 tests)
- ✅ TestTagWeightFeedback: 3 tests
- ✅ TestTrendingIntegration: 3 tests (1 skipped - requires LLM)
- ✅ TestCrossSystemDataFlow: 3 tests
- ✅ TestE2EIntegrationWorkflows: 1 test (1 skipped - requires sniffer)

### Skipped Tests (5 tests)
- ⏭️ TestSnifferToKBFlow: 3 tests (require external sniffer service)
- ⏭️ TestTrendingIntegration: 1 test (requires LLM configuration)
- ⏭️ TestE2EIntegrationWorkflows: 1 test (requires sniffer service)

## Expected Output

```
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_kb_addition_increments_tag_weights PASSED
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_multiple_kb_additions_accumulate_weight PASSED
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_tag_weights_influence_trending_order PASSED
...
========== 10 passed, 5 skipped in XXs ==========
```

## Troubleshooting

### Service Not Available
```bash
# Check if service is running
curl http://localhost:8000/healthz

# Start service if not running
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Port Already in Use
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F
```

### Tests Fail with Cleanup Warnings
This is normal - cleanup warnings don't affect test results. They indicate resources that couldn't be cleaned up (usually because they don't exist).

## Integration with Other Tests

```bash
# Run all E2E tests (P0 + P2 + P3)
pytest tests/e2e/ -v -s

# Run specific test suites
pytest tests/e2e/test_e2e_news_system.py -v -s      # P0: News/Trending
pytest tests/e2e/test_e2e_kb_system.py -v -s        # P2: KB System
pytest tests/e2e/test_e2e_integration.py -v -s      # P3: Integration
```

## Test Coverage

P3 tests validate:
- ✅ Tag weight feedback loops (KB → Tags)
- ✅ Cross-system data flow (Source → Resource → KB → Trending)
- ✅ Resource lifecycle across systems
- ✅ Complete user workflows
- ✅ Data consistency and integrity

For detailed documentation, see: `tests/e2e/P3_IMPLEMENTATION_SUMMARY.md`
