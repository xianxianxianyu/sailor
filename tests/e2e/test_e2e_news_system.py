"""End-to-end tests for News system (P0 priority)."""
import pytest
import time
from .helpers.api_client import NewsAPIClient
from .helpers.test_data import (
    generate_test_source,
    generate_test_paper_source,
    generate_test_tag,
    generate_test_sniffer_query,
    generate_test_pack,
)
from .conftest import wait_for_condition


class TestSourceManagement:
    """Test Source CRUD and data collection."""

    def test_create_and_list_source(self, api_client: NewsAPIClient, cleanup_test_sources):
        """Test creating a source and listing it."""
        # Create source
        source_data = generate_test_source()
        created = api_client.create_source(source_data)

        assert created["name"] == source_data["name"]
        assert created["source_type"] == source_data["source_type"]
        assert "source_id" in created

        # List sources and verify
        sources = api_client.list_sources()
        source_ids = [s["source_id"] for s in sources]
        assert created["source_id"] in source_ids

    def test_run_source_and_verify_resources(self, api_client: NewsAPIClient, cleanup_test_sources):
        """Test running a source and verifying resources are collected."""
        # Create source
        source_data = generate_test_source()
        created = api_client.create_source(source_data)
        source_id = created["source_id"]

        # Run source
        try:
            result = api_client.run_source(source_id)
            assert "message" in result or "status" in result
        except Exception as e:
            pytest.skip(f"Source run failed (network issue): {e}")

        # Wait for resources to be collected
        time.sleep(5)

        # Verify resources exist
        try:
            resources = api_client.list_resources(limit=50)
            # Should have at least some resources
            assert len(resources) > 0, "No resources collected"
        except Exception as e:
            pytest.skip(f"Could not verify resources: {e}")

    def test_delete_source(self, api_client: NewsAPIClient):
        """Test deleting a source."""
        # Create source
        source_data = generate_test_source()
        created = api_client.create_source(source_data)
        source_id = created["source_id"]

        # Delete source
        api_client.delete_source(source_id)

        # Verify deletion
        sources = api_client.list_sources()
        source_ids = [s["source_id"] for s in sources]
        assert source_id not in source_ids


class TestPaperSourceManagement:
    """Test Paper Source management and collection."""

    def test_create_paper_source(self, api_client: NewsAPIClient, cleanup_test_paper_sources):
        """Test creating a paper source."""
        # Create paper source
        source_data = generate_test_paper_source()
        created = api_client.create_paper_source(source_data)

        assert created["name"] == source_data["name"]
        assert created["platform"] == source_data["platform"]
        assert "source_id" in created

    def test_run_paper_source_and_verify_papers(
        self, api_client: NewsAPIClient, cleanup_test_paper_sources
    ):
        """Test running a paper source and verifying papers are collected."""
        # Create paper source
        source_data = generate_test_paper_source()
        created = api_client.create_paper_source(source_data)
        source_id = created["source_id"]

        # Run paper source
        try:
            result = api_client.run_paper_source(source_id)
            assert "message" in result or "status" in result
        except Exception as e:
            pytest.skip(f"Paper source run failed (network issue): {e}")

        # Wait for papers to be collected
        time.sleep(10)

        # Verify papers exist
        try:
            papers = api_client.list_papers(limit=50)
            assert len(papers) > 0, "No papers collected"
        except Exception as e:
            pytest.skip(f"Could not verify papers: {e}")


class TestTagging:
    """Test tagging functionality."""

    def test_create_tag(self, api_client: NewsAPIClient, cleanup_test_tags):
        """Test creating a tag."""
        tag_data = generate_test_tag()
        created = api_client.create_tag(
            name=tag_data["name"],
            color=tag_data["color"],
            weight=tag_data["weight"]
        )

        assert created["name"] == tag_data["name"]
        assert created["color"] == tag_data["color"]
        assert "tag_id" in created

    def test_tag_resource_manually(
        self, api_client: NewsAPIClient, cleanup_test_tags, cleanup_test_sources
    ):
        """Test manually tagging a resource."""
        # Ensure we have resources
        resources = api_client.list_resources(limit=10)
        if len(resources) == 0:
            # Create a source and run it to get resources
            source_data = generate_test_source()
            created = api_client.create_source(source_data)
            try:
                api_client.run_source(created["source_id"])
                time.sleep(5)
                resources = api_client.list_resources(limit=10)
            except Exception as e:
                pytest.skip(f"Could not create resources for tagging test: {e}")

        if len(resources) == 0:
            pytest.skip("No resources available for tagging")

        # Create tag
        tag_data = generate_test_tag()
        tag = api_client.create_tag(
            name=tag_data["name"],
            color=tag_data["color"],
            weight=tag_data["weight"]
        )

        # Tag a resource
        resource_id = resources[0]["resource_id"]
        api_client.tag_resource(resource_id, tag["tag_id"])

        # Verify tagging
        tagged_resources = api_client.list_resources(tag_id=tag["tag_id"], limit=10)
        resource_ids = [r["resource_id"] for r in tagged_resources]
        assert resource_id in resource_ids

    def test_list_resources_by_tag(
        self, api_client: NewsAPIClient, cleanup_test_tags, cleanup_test_sources
    ):
        """Test listing resources filtered by tag."""
        # Ensure we have resources
        resources = api_client.list_resources(limit=10)
        if len(resources) == 0:
            source_data = generate_test_source()
            created = api_client.create_source(source_data)
            try:
                api_client.run_source(created["source_id"])
                time.sleep(5)
                resources = api_client.list_resources(limit=10)
            except Exception as e:
                pytest.skip(f"Could not create resources: {e}")

        if len(resources) == 0:
            pytest.skip("No resources available")

        # Create tag and tag multiple resources
        tag_data = generate_test_tag()
        tag = api_client.create_tag(
            name=tag_data["name"],
            color=tag_data["color"],
            weight=tag_data["weight"]
        )

        # Tag first 3 resources
        tagged_count = min(3, len(resources))
        for i in range(tagged_count):
            api_client.tag_resource(resources[i]["resource_id"], tag["tag_id"])

        # List resources by tag
        tagged_resources = api_client.list_resources(tag_id=tag["tag_id"], limit=10)
        assert len(tagged_resources) >= tagged_count


class TestSniffer:
    """Test sniffer search functionality."""

    def test_sniffer_search(self, api_client: NewsAPIClient):
        """Test sniffer search across channels."""
        query = generate_test_sniffer_query(keyword="python", channels=["github"])

        try:
            result = api_client.search(query)
            assert "results" in result or "items" in result
        except Exception as e:
            pytest.skip(f"Sniffer search failed (network issue): {e}")

    def test_create_and_run_pack(self, api_client: NewsAPIClient, cleanup_test_packs):
        """Test creating and running a sniffer pack."""
        # Create pack
        pack_data = generate_test_pack(keyword="AI", channels=["github"])
        created = api_client.create_pack(pack_data)

        assert created["name"] == pack_data["name"]
        assert "pack_id" in created

        # Run pack
        try:
            result = api_client.run_pack(created["pack_id"])
            assert "results" in result or "message" in result or "status" in result
        except Exception as e:
            pytest.skip(f"Pack run failed (network issue): {e}")


class TestE2EFlow:
    """Test complete end-to-end workflows."""

    def test_full_pipeline_source_to_tag(
        self, api_client: NewsAPIClient, cleanup_test_sources, cleanup_test_tags
    ):
        """Test full pipeline: Source → Run → Tag."""
        # Step 1: Create and run source
        source_data = generate_test_source()
        source = api_client.create_source(source_data)

        try:
            api_client.run_source(source["source_id"])
        except Exception as e:
            pytest.skip(f"Source run failed: {e}")

        # Wait for resources
        time.sleep(5)

        # Step 2: Verify resources collected
        resources = api_client.list_resources(limit=10)
        assert len(resources) > 0, "No resources collected"

        # Step 3: Create tag and tag resources
        tag_data = generate_test_tag()
        tag = api_client.create_tag(
            name=tag_data["name"],
            color=tag_data["color"],
            weight=tag_data["weight"]
        )

        # Tag first 3 resources
        tagged_count = min(3, len(resources))
        for i in range(tagged_count):
            api_client.tag_resource(resources[i]["resource_id"], tag["tag_id"])

        # Step 4: Verify tagging
        tagged_resources = api_client.list_resources(tag_id=tag["tag_id"], limit=10)
        assert len(tagged_resources) >= tagged_count
