# KB (Knowledge Base) System E2E Tests (P2)

## Overview

This directory contains end-to-end automated tests for the Sailor KB (Knowledge Base) system. These tests verify the complete workflow from KB creation to graph building and report generation.

## Test Coverage

### Test Classes

1. **TestKBManagement** - KB CRUD operations
   - Create and list KBs
   - Delete KBs

2. **TestKBItems** - Item management in KBs
   - Add resources to KB
   - List KB items
   - Remove items from KB
   - Query resource-KB associations

3. **TestResourceAnalysis** - LLM-powered analysis
   - Analyze single resource
   - Get analysis results
   - Batch analyze resources

4. **TestKBReports** - Report generation
   - Generate KB reports (cluster, association, summary)
   - List reports
   - Get latest report by type

5. **TestKBGraph** - Knowledge graph operations
   - Create edges between resources
   - Get full KB graph
   - Freeze/unfreeze edges
   - Delete edges

6. **TestE2EKBFlow** - Complete end-to-end workflows
   - Full pipeline: KB → Items → Analysis → Reports → Graph

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

3. **Ensure you have resources in the database:**
   - KB tests require existing resources to add to KBs
   - Run News/Trending tests first to populate resources, or
   - Manually create some sources and run them

## Running Tests

### Run all P2 tests
```bash
pytest tests/e2e/test_e2e_kb_system.py -v -s
```

### Run specific test class
```bash
pytest tests/e2e/test_e2e_kb_system.py::TestKBManagement -v -s
pytest tests/e2e/test_e2e_kb_system.py::TestKBGraph -v -s
pytest tests/e2e/test_e2e_kb_system.py::TestE2EKBFlow -v -s
```

### Run specific test
```bash
pytest tests/e2e/test_e2e_kb_system.py::TestE2EKBFlow::test_full_kb_pipeline -v -s
```

### Generate HTML report
```bash
pytest tests/e2e/test_e2e_kb_system.py -v --html=report_kb.html --self-contained-html
```

## Test Execution Notes

### LLM Dependencies
- Resource analysis tests require LLM configuration
- Report generation tests require LLM configuration
- **Tests will skip if LLM is not available** (not marked as failures)

### Data Dependencies
- Most tests require existing resources in the database
- Tests will skip if insufficient resources available
- Recommended: Run P0 News/Trending tests first to populate data

### Timing
- KB CRUD operations: < 1 second
- Analysis operations: 5-10 seconds (LLM calls)
- Report generation: 10-30 seconds (LLM calls)
- Full E2E pipeline: 30-60 seconds

### Cleanup
- All test KBs use `test-` prefix
- Fixtures automatically clean up after each test
- Deleting a KB cascades to items and graph edges

## Success Criteria

- ✅ All tests pass (>= 95% pass rate)
- ✅ KB creation and management works
- ✅ Items can be added/removed from KBs
- ✅ Resource analysis completes (if LLM configured)
- ✅ Reports generate successfully (if LLM configured)
- ✅ Graph edges can be created and managed
- ✅ End-to-end pipeline completes

## Test Scenarios

### Scenario 1: KB Management
1. Create KB → ✅
2. List KBs → ✅
3. Delete KB → ✅

### Scenario 2: KB Items
1. Add resource to KB → ✅
2. List KB items → ✅
3. Remove item from KB → ✅
4. Query resource's KBs → ✅

### Scenario 3: Resource Analysis
1. Analyze single resource → ✅
2. Get analysis result → ✅
3. Batch analyze resources → ✅

### Scenario 4: KB Reports
1. Generate reports (cluster/association/summary) → ✅
2. List reports → ✅
3. Get latest report by type → ✅

### Scenario 5: Knowledge Graph
1. Create edge between resources → ✅
2. Get full KB graph → ✅
3. Freeze/unfreeze edge → ✅
4. Delete edge → ✅

### Scenario 6: End-to-End Pipeline
1. Create KB → ✅
2. Add items → ✅
3. Analyze resources → ✅
4. Generate reports → ✅
5. Build graph → ✅

## Troubleshooting

### No resources available
```
SKIPPED: No resources available for KB item test
```
**Solution:** Run P0 News/Trending tests first to populate resources

### LLM not configured
```
SKIPPED: Analysis failed (LLM may not be configured)
```
**Solution:** This is expected if LLM is not set up. Tests will skip gracefully.

### Service not available
```
Error: Service not available at http://localhost:8000
```
**Solution:** Start the backend service first

## API Client Usage

The `KBAPIClient` class provides methods for all KB APIs:

```python
from tests.e2e.helpers.kb_api_client import KBAPIClient

client = KBAPIClient(base_url="http://localhost:8000")

# KB Management
kb = client.create_kb(name="My KB", description="Test KB")
kbs = client.list_kbs()
client.delete_kb(kb_id)

# KB Items
client.add_item_to_kb(kb_id, resource_id)
items = client.list_kb_items(kb_id)
client.remove_item_from_kb(kb_id, resource_id)

# Analysis
client.analyze_resource(resource_id)
analysis = client.get_resource_analysis(resource_id)

# Reports
reports = client.generate_kb_reports(kb_id)
latest = client.get_latest_kb_report(kb_id, "cluster")

# Graph
graph = client.get_kb_graph(kb_id)
client.create_graph_edge(kb_id, node_a, node_b, reason)
client.freeze_graph_edge(kb_id, node_a, node_b)
```

## File Structure

```
tests/e2e/
├── test_e2e_kb_system.py            # Main KB test file
├── conftest.py                      # Fixtures (includes kb_client)
└── helpers/
    ├── kb_api_client.py             # KB API client wrapper
    └── kb_test_data.py              # KB test data generators
```

## Integration with Other Systems

KB system integrates with:
- **News/Trending**: Resources from sources can be added to KBs
- **Tagging**: Tag weights increment when resources added to KB
- **Analysis**: LLM analyzes resources and recommends KBs

## Next Steps

After P2 KB tests are complete:
- **P3:** Cross-system integration tests
- **P4:** Performance and load testing
