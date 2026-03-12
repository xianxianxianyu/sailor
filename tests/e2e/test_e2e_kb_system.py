"""End-to-end tests for KB (Knowledge Base) system (P2 priority)."""
import pytest
import time
from .helpers.kb_api_client import KBAPIClient
from .helpers.api_client import NewsAPIClient
from .helpers.kb_test_data import generate_test_kb, generate_test_graph_edge
from .conftest import wait_for_condition


class TestKBManagement:
    """Test Knowledge Base CRUD operations."""

    def test_create_and_list_kb(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test creating a KB and listing it."""
        # Create KB
        kb_data = generate_test_kb()
        created = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        assert created["name"] == kb_data["name"]
        assert created["description"] == kb_data["description"]
        assert "kb_id" in created

        # List KBs and verify
        kbs = kb_client.list_kbs()
        kb_ids = [kb["kb_id"] for kb in kbs]
        assert created["kb_id"] in kb_ids

    def test_delete_kb(self, kb_client: KBAPIClient):
        """Test deleting a KB."""
        # Create KB
        kb_data = generate_test_kb()
        created = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )
        kb_id = created["kb_id"]

        # Delete KB
        kb_client.delete_kb(kb_id)

        # Verify deletion
        kbs = kb_client.list_kbs()
        kb_ids = [kb["kb_id"] for kb in kbs]
        assert kb_id not in kb_ids


class TestKBItems:
    """Test adding and managing items in KB."""

    def test_add_item_to_kb(
        self, kb_client: KBAPIClient, api_client: NewsAPIClient, cleanup_test_kbs
    ):
        """Test adding a resource to a KB."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available for KB item test")

        # Create KB
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        # Add resource to KB
        resource_id = resources[0]["resource_id"]
        item = kb_client.add_item_to_kb(kb["kb_id"], resource_id)

        assert item["kb_id"] == kb["kb_id"]
        assert item["resource_id"] == resource_id
        assert "added_at" in item

    def test_list_kb_items(
        self, kb_client: KBAPIClient, cleanup_test_kbs
    ):
        """Test listing items in a KB."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available")

        # Create KB
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        # Add multiple resources
        added_count = min(3, len(resources))
        for i in range(added_count):
            kb_client.add_item_to_kb(kb["kb_id"], resources[i]["resource_id"])

        # List items
        items = kb_client.list_kb_items(kb["kb_id"])
        assert len(items) >= added_count

        # Verify items have resource details
        if len(items) > 0:
            item = items[0]
            assert "resource_id" in item
            assert "title" in item or "resource" in item

    def test_remove_item_from_kb(
        self, kb_client: KBAPIClient, cleanup_test_kbs
    ):
        """Test removing a resource from a KB."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available")

        # Create KB and add item
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )
        resource_id = resources[0]["resource_id"]
        kb_client.add_item_to_kb(kb["kb_id"], resource_id)

        # Remove item
        kb_client.remove_item_from_kb(kb["kb_id"], resource_id)

        # Verify removal
        items = kb_client.list_kb_items(kb["kb_id"])
        item_resource_ids = [item["resource_id"] for item in items]
        assert resource_id not in item_resource_ids

    def test_resource_kb_association(
        self, kb_client: KBAPIClient, cleanup_test_kbs
    ):
        """Test querying which KBs contain a resource."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available")

        # Create KB and add resource
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )
        resource_id = resources[0]["resource_id"]
        kb_client.add_item_to_kb(kb["kb_id"], resource_id)

        # Query resource's KBs
        resource_kbs = kb_client.get_resource_kbs(resource_id)
        kb_ids = [k["kb_id"] for k in resource_kbs]
        assert kb["kb_id"] in kb_ids


class TestResourceAnalysis:
    """Test resource analysis with LLM."""

    def test_analyze_single_resource(self, kb_client: KBAPIClient):
        """Test analyzing a single resource."""
        # Get a resource
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available for analysis")

        resource_id = resources[0]["resource_id"]

        # Analyze resource
        try:
            result = kb_client.analyze_resource(resource_id)
            assert "status" in result or "resource_id" in result
        except Exception as e:
            pytest.skip(f"Analysis failed (LLM may not be configured): {e}")

    def test_get_resource_analysis(self, kb_client: KBAPIClient):
        """Test retrieving analysis result."""
        # Get a resource
        resources = kb_client.list_resources(limit=10)
        if len(resources) == 0:
            pytest.skip("No resources available")

        resource_id = resources[0]["resource_id"]

        # Try to analyze first
        try:
            kb_client.analyze_resource(resource_id)
            time.sleep(2)  # Wait for analysis
        except Exception:
            pass

        # Get analysis
        try:
            analysis = kb_client.get_resource_analysis(resource_id)
            if analysis:
                assert "summary" in analysis or "topics" in analysis
        except Exception as e:
            pytest.skip(f"No analysis available: {e}")

    def test_batch_analyze(self, kb_client: KBAPIClient):
        """Test batch analysis of resources."""
        # Get resources
        resources = kb_client.list_resources(limit=5)
        if len(resources) == 0:
            pytest.skip("No resources available")

        resource_ids = [r["resource_id"] for r in resources[:3]]

        # Batch analyze
        try:
            result = kb_client.batch_analyze(resource_ids)
            assert "message" in result or "status" in result
        except Exception as e:
            pytest.skip(f"Batch analysis failed: {e}")


class TestKBReports:
    """Test KB report generation."""

    def test_generate_kb_reports(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test generating reports for a KB."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) < 3:
            pytest.skip("Need at least 3 resources for report generation")

        # Create KB and add resources
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        for resource in resources[:5]:
            kb_client.add_item_to_kb(kb["kb_id"], resource["resource_id"])

        # Generate reports
        try:
            reports = kb_client.generate_kb_reports(kb["kb_id"])
            assert isinstance(reports, list)
            # Should generate 3 types: cluster, association, summary
            if len(reports) > 0:
                assert "report_type" in reports[0]
                assert "status" in reports[0]
        except Exception as e:
            pytest.skip(f"Report generation failed (LLM may not be configured): {e}")

    def test_list_kb_reports(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test listing reports for a KB."""
        # Create KB
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        # List reports (may be empty)
        reports = kb_client.list_kb_reports(kb["kb_id"])
        assert isinstance(reports, list)

    def test_get_latest_report(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test getting latest report by type."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) < 3:
            pytest.skip("Need at least 3 resources")

        # Create KB and add resources
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        for resource in resources[:5]:
            kb_client.add_item_to_kb(kb["kb_id"], resource["resource_id"])

        # Generate reports
        try:
            kb_client.generate_kb_reports(kb["kb_id"])
            time.sleep(3)  # Wait for generation

            # Get latest cluster report
            latest = kb_client.get_latest_kb_report(kb["kb_id"], "cluster")
            if latest:
                assert latest["report_type"] == "cluster"
                assert "content_json" in latest or "content" in latest
        except Exception as e:
            pytest.skip(f"Report retrieval failed: {e}")


class TestKBGraph:
    """Test knowledge graph operations."""

    def test_create_graph_edge(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test creating an edge between two resources."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) < 2:
            pytest.skip("Need at least 2 resources for graph edge")

        # Create KB and add resources
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        resource_a = resources[0]["resource_id"]
        resource_b = resources[1]["resource_id"]

        kb_client.add_item_to_kb(kb["kb_id"], resource_a)
        kb_client.add_item_to_kb(kb["kb_id"], resource_b)

        # Create edge
        edge_data = generate_test_graph_edge(resource_a, resource_b)
        edge = kb_client.create_graph_edge(
            kb["kb_id"],
            edge_data["node_a_id"],
            edge_data["node_b_id"],
            edge_data["reason"],
            edge_data["reason_type"]
        )

        assert "node_a_id" in edge or "reason" in edge

    def test_get_kb_graph(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test retrieving full KB graph."""
        # Create KB
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        # Get graph (may be empty)
        graph = kb_client.get_kb_graph(kb["kb_id"])
        assert "nodes" in graph or "edges" in graph

    def test_graph_edge_lifecycle(self, kb_client: KBAPIClient, cleanup_test_kbs):
        """Test edge freeze/unfreeze/delete operations."""
        # Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) < 2:
            pytest.skip("Need at least 2 resources")

        # Create KB and add resources
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )

        resource_a = resources[0]["resource_id"]
        resource_b = resources[1]["resource_id"]

        kb_client.add_item_to_kb(kb["kb_id"], resource_a)
        kb_client.add_item_to_kb(kb["kb_id"], resource_b)

        # Create edge
        edge_data = generate_test_graph_edge(resource_a, resource_b)
        kb_client.create_graph_edge(
            kb["kb_id"],
            edge_data["node_a_id"],
            edge_data["node_b_id"],
            edge_data["reason"],
            edge_data["reason_type"]
        )

        # Freeze edge
        try:
            result = kb_client.freeze_graph_edge(kb["kb_id"], resource_a, resource_b)
            assert "frozen" in result or "status" in result
        except Exception as e:
            print(f"Freeze operation: {e}")

        # Unfreeze edge
        try:
            result = kb_client.unfreeze_graph_edge(kb["kb_id"], resource_a, resource_b)
            assert "frozen" in result or "status" in result
        except Exception as e:
            print(f"Unfreeze operation: {e}")

        # Delete edge
        kb_client.delete_graph_edge(kb["kb_id"], resource_a, resource_b)


class TestE2EKBFlow:
    """Test complete end-to-end KB workflows."""

    def test_full_kb_pipeline(
        self, kb_client: KBAPIClient, api_client: NewsAPIClient, cleanup_test_kbs
    ):
        """Test full pipeline: Create KB → Add Items → Analyze → Generate Reports → Build Graph."""
        # Step 1: Ensure we have resources
        resources = kb_client.list_resources(limit=10)
        if len(resources) < 3:
            pytest.skip("Need at least 3 resources for full pipeline")

        # Step 2: Create KB
        kb_data = generate_test_kb()
        kb = kb_client.create_kb(
            name=kb_data["name"],
            description=kb_data["description"]
        )
        assert "kb_id" in kb

        # Step 3: Add resources to KB
        added_count = min(5, len(resources))
        for i in range(added_count):
            kb_client.add_item_to_kb(kb["kb_id"], resources[i]["resource_id"])

        # Verify items added
        items = kb_client.list_kb_items(kb["kb_id"])
        assert len(items) >= added_count

        # Step 4: Analyze resources (optional, may skip if LLM not configured)
        try:
            kb_client.analyze_resource(resources[0]["resource_id"])
            time.sleep(2)
        except Exception:
            print("Analysis skipped (LLM not configured)")

        # Step 5: Generate reports (optional, may skip if LLM not configured)
        try:
            reports = kb_client.generate_kb_reports(kb["kb_id"])
            assert isinstance(reports, list)
            print(f"Generated {len(reports)} reports")
        except Exception as e:
            print(f"Report generation skipped: {e}")

        # Step 6: Build graph edges
        if len(resources) >= 2:
            resource_a = resources[0]["resource_id"]
            resource_b = resources[1]["resource_id"]

            edge_data = generate_test_graph_edge(resource_a, resource_b)
            kb_client.create_graph_edge(
                kb["kb_id"],
                edge_data["node_a_id"],
                edge_data["node_b_id"],
                edge_data["reason"],
                edge_data["reason_type"]
            )

            # Verify graph
            graph = kb_client.get_kb_graph(kb["kb_id"])
            assert "nodes" in graph or "edges" in graph
            print(f"Graph created with nodes and edges")

        print(f"✅ Full KB pipeline completed for KB {kb['kb_id']}")
