# Sailor E2E Tests

## Overview

This directory contains end-to-end automated tests for the Sailor system. Tests are organized by priority:

- **P0: News/Trending System** - Source management, tagging, trending reports, sniffer
- **P1: Follow System** - Located in `sailor/tests/test_e2e_follow_auto.py`
- **P2: KB (Knowledge Base) System** - KB management, analysis, reports, knowledge graph
- **P3: Cross-system Integration** - (Future)

## Quick Start

### Run All E2E Tests
```bash
# P0: News/Trending
pytest tests/e2e/test_e2e_news_system.py -v -s

# P2: KB System
pytest tests/e2e/test_e2e_kb_system.py -v -s

# All tests
pytest tests/e2e/ -v -s
```

---

# P0: News/Trending System E2E Tests

## Overview

Tests for the News/Trending system verify the complete workflow from source creation to trending report generation.

## Test Coverage

### Test Classes

1. **TestSourceManagement** - Source CRUD and data collection
   - Create and list sources
   - Run source and verify resources collected
   - Delete sources

2. **TestPaperSourceManagement** - Paper source management
   - Create paper sources (arXiv)
   - Run paper sources and verify papers collected

3. **TestTagging** - Tagging functionality
   - Create tags
   - Tag resources manually
   - List resources by tag

4. **TestTrending** - Trending report generation
   - Generate trending reports
   - Verify report structure with tagged resources

5. **TestSniffer** - Multi-channel search
   - Search across channels (GitHub, HN, etc.)
   - Create and run sniffer packs

6. **TestE2EFlow** - Complete end-to-end workflows
   - Full pipeline: Source → Run → Tag → Trending

## Prerequisites

1. **Start the backend service:**
   ```bash
   cd /e/OS/sailor
   python -m uvicorn backend.app.main:app --reload --port 8000
   ```

2. **Verify service is running:**
   ```bash
   curl http://localhost:8000/healthz
   ```

## Running Tests

### Run all P0 tests
```bash
pytest tests/e2e/test_e2e_news_system.py -v -s
```

### Run specific test class
```bash
pytest tests/e2e/test_e2e_news_system.py::TestSourceManagement -v -s
pytest tests/e2e/test_e2e_news_system.py::TestTagging -v -s
pytest tests/e2e/test_e2e_news_system.py::TestE2EFlow -v -s
```

### Run specific test
```bash
pytest tests/e2e/test_e2e_news_system.py::TestE2EFlow::test_full_pipeline_source_to_trending -v -s
```

### Generate HTML report
```bash
pytest tests/e2e/test_e2e_news_system.py -v --html=report_news.html --self-contained-html
```

### Run with verbose output
```bash
pytest tests/e2e/test_e2e_news_system.py -v -s --tb=short
```

## Test Execution Notes

### Network Dependencies
- RSS Source tests require external RSS feeds (may fail if network unavailable)
- Paper Source tests require arXiv API access (may timeout)
- Sniffer tests require access to GitHub, HN, etc.
- **Network failures are marked as `skip` rather than `fail`**

### Data Cleanup
- All test data uses `test-` prefix for identification
- Fixtures automatically clean up after each test
- Manual cleanup available if needed

### Timing
- Source runs may take 5-10 seconds
- Paper source runs may take 10-30 seconds
- Full E2E pipeline may take 30-60 seconds
- Total test suite: ~5-10 minutes

### Concurrency
- Tests run serially by default (SQLite lock considerations)
- Do not use `-n` flag for parallel execution
- Each test uses isolated test data

## Success Criteria

- ✅ All tests pass (>= 95% pass rate)
- ✅ Source creation and data collection works
- ✅ Tagging system functions correctly
- ✅ Trending reports generate successfully
- ✅ Sniffer searches return results
- ✅ End-to-end pipeline completes without errors

## Troubleshooting

### Service not available
```
Error: Service not available at http://localhost:8000
```
**Solution:** Start the backend service first

### Network timeouts
```
SKIPPED: Source run failed (network issue)
```
**Solution:** This is expected behavior for network-dependent tests

### Database locked
```
Error: database is locked
```
**Solution:** Run tests serially (without `-n` flag)

### No resources collected
```
AssertionError: No resources collected
```
**Solution:** Check if RSS feed is accessible, or test will skip

## File Structure

```
tests/e2e/
├── __init__.py
├── conftest.py                      # Fixtures and configuration
├── test_e2e_news_system.py          # Main test file
└── helpers/
    ├── __init__.py
    ├── api_client.py                # API client wrapper
    └── test_data.py                 # Test data generators
```

## API Client Usage

The `NewsAPIClient` class provides methods for all News/Trending APIs:

```python
from tests.e2e.helpers.api_client import NewsAPIClient

client = NewsAPIClient(base_url="http://localhost:8000")

# Sources
source = client.create_source(data)
client.run_source(source_id)
sources = client.list_sources()

# Tags
tag = client.create_tag(name, color)
client.tag_resource(resource_id, tag_id)

# Trending
report = client.get_trending()

# Sniffer
results = client.search(query)
```

## Next Steps (Future Priorities)

- **P1:** Follow system E2E tests
- **P2:** KB system E2E tests
- **P3:** Integration tests across systems
- **P4:** Performance and load testing
