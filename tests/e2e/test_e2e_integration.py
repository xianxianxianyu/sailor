"""P3: Cross-system integration tests for Sailor.

Tests the integration points between different subsystems:
- Tag weight feedback loops
- Sniffer → Resource → KB data flow
- Cross-system data flow
- End-to-end user workflows
"""
import pytest
import time
from .helpers.api_client import NewsAPIClient
from .helpers.kb_api_client import KBAPIClient
from .helpers.integration_helpers import (
    get_tag_weight,
    verify_tag_weight_increased,
    create_test_resource_with_tags,
    verify_provenance_chain,
    wait_for_resources,
    create_kb_with_resource,
)


class TestTagWeightFeedback:
    """Test tag weight feedback loops between KB and tagging system."""

    def test_kb_addition_increments_tag_weights(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that adding a resource to KB increments its tag weights."""
        # Create tag with initial weight
        tag = api_client.create_tag("test-tag-weight-1", weight=1)
        tag_id = tag["tag_id"]
        initial_weight = get_tag_weight(api_client, tag_id)

        # Create source and run to get resource
        source_data = {
            "name": "test-source-weight-1",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        # Get resource and tag it
        resources = api_client.list_resources(limit=1)
        assert len(resources) > 0, "No resources created"
        resource_id = resources[0]["resource_id"]
        api_client.tag_resource(resource_id, tag_id)

        # Create KB and add resource
        kb_data = {"name": "test-kb-weight-1", "description": "Test KB"}
        kb = kb_client.create_kb(kb_data)
        kb_client.add_resource_to_kb(kb["kb_id"], resource_id)

        # Verify tag weight increased by 1
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 1)

    def test_multiple_kb_additions_accumulate_weight(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that adding same resource to multiple KBs accumulates tag weight."""
        # Create 2 tags
        tag1 = api_client.create_tag("test-tag-multi-1", weight=1)
        tag2 = api_client.create_tag("test-tag-multi-2", weight=1)
        tag1_id = tag1["tag_id"]
        tag2_id = tag2["tag_id"]

        initial_weight1 = get_tag_weight(api_client, tag1_id)
        initial_weight2 = get_tag_weight(api_client, tag2_id)

        # Create resource with both tags
        source_data = {
            "name": "test-source-multi-kb",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        resources = api_client.list_resources(limit=1)
        resource_id = resources[0]["resource_id"]
        api_client.tag_resource(resource_id, tag1_id)
        api_client.tag_resource(resource_id, tag2_id)

        # Create 3 KBs and add resource to each
        for i in range(3):
            kb_data = {"name": f"test-kb-multi-{i}", "description": f"Test KB {i}"}
            kb = kb_client.create_kb(kb_data)
            kb_client.add_resource_to_kb(kb["kb_id"], resource_id)

        # Verify both tags increased by 3
        verify_tag_weight_increased(api_client, tag1_id, initial_weight1, 3)
        verify_tag_weight_increased(api_client, tag2_id, initial_weight2, 3)

    def test_tag_weights_verified_after_kb_boost(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that tag weights increase after KB boost."""
        # Create 2 tags with same initial weight
        tag_high = api_client.create_tag("test-tag-high-weight", weight=1)
        tag_low = api_client.create_tag("test-tag-low-weight", weight=1)
        tag_high_id = tag_high["tag_id"]
        tag_low_id = tag_low["tag_id"]

        # Create 2 resources with different tags
        source_data = {
            "name": "test-source-weight-verify",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        resources = api_client.list_resources(limit=2)
        assert len(resources) >= 2, "Need at least 2 resources"

        resource_high = resources[0]["resource_id"]
        resource_low = resources[1]["resource_id"]

        api_client.tag_resource(resource_high, tag_high_id)
        api_client.tag_resource(resource_low, tag_low_id)

        # Boost tag_high by adding to 5 KBs
        for i in range(5):
            kb_data = {"name": f"test-kb-high-{i}", "description": f"KB {i}"}
            kb = kb_client.create_kb(kb_data)
            kb_client.add_resource_to_kb(kb["kb_id"], resource_high)

        # Boost tag_low by adding to 1 KB
        kb_data = {"name": "test-kb-low-1", "description": "KB low"}
        kb = kb_client.create_kb(kb_data)
        kb_client.add_resource_to_kb(kb["kb_id"], resource_low)

        # Verify tag_high has higher weight
        tag_high_weight = get_tag_weight(api_client, tag_high_id)
        tag_low_weight = get_tag_weight(api_client, tag_low_id)
        assert tag_high_weight > tag_low_weight, "High weight tag should have higher weight"


class TestSnifferToKBFlow:
    """Test Sniffer → Resource → KB data flow with provenance."""

    @pytest.mark.skip(reason="Requires external sniffer service")
    def test_sniffer_result_to_kb_with_provenance(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test saving sniffer result to KB preserves provenance."""
        # Execute sniffer search
        query = {
            "keyword": "python",
            "channels": ["github"],
            "limit": 1
        }
        result = api_client.search(query)
        assert "results" in result
        assert len(result["results"]) > 0

        sniffer_result = result["results"][0]
        sniffer_result_id = sniffer_result["result_id"]

        # Create KB
        kb_data = {"name": "test-kb-sniffer-1", "description": "Sniffer test KB"}
        kb = kb_client.create_kb(kb_data)
        kb_id = kb["kb_id"]

        # Save sniffer result to KB (this should create resource with provenance)
        save_data = {
            "kb_id": kb_id,
            "sniffer_result_id": sniffer_result_id
        }
        response = api_client.session.post(
            f"{api_client.base_url}/sniffer/save-to-kb",
            json=save_data
        )
        response.raise_for_status()
        saved = response.json()

        resource_id = saved["resource_id"]

        # Verify provenance
        verify_provenance_chain(kb_client, resource_id, "sniffer:github")

        # Verify KB contains resource
        kb_items = kb_client.list_kb_items(kb_id)
        resource_ids = [item["resource_id"] for item in kb_items]
        assert resource_id in resource_ids

    @pytest.mark.skip(reason="Requires external sniffer service")
    def test_sniffer_provenance_chain_maintained(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that provenance chain is maintained through sniffer → resource → KB."""
        # Execute sniffer search and save
        query = {"keyword": "machine learning", "channels": ["arxiv"], "limit": 1}
        result = api_client.search(query)
        sniffer_result_id = result["results"][0]["result_id"]

        # Create KB and save result
        kb = kb_client.create_kb({"name": "test-kb-provenance", "description": "Test"})
        kb_id = kb["kb_id"]

        save_data = {"kb_id": kb_id, "sniffer_result_id": sniffer_result_id}
        response = api_client.session.post(
            f"{api_client.base_url}/sniffer/save-to-kb",
            json=save_data
        )
        resource_id = response.json()["resource_id"]

        # Verify provenance chain
        resource = kb_client.get_resource(resource_id)
        assert "provenance" in resource
        assert resource["provenance"]["sniffer_result_id"] == sniffer_result_id
        assert resource["provenance"]["channel"] == "arxiv"

        # Verify bidirectional queries work
        kb_items = kb_client.list_kb_items(kb_id)
        assert any(item["resource_id"] == resource_id for item in kb_items)

    @pytest.mark.skip(reason="Requires external sniffer service")
    def test_multiple_sniffer_channels_to_kb(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test saving results from multiple sniffer channels to same KB."""
        # Create KB
        kb = kb_client.create_kb({"name": "test-kb-multi-channel", "description": "Test"})
        kb_id = kb["kb_id"]

        channels = ["github", "arxiv"]
        resource_ids = []

        for channel in channels:
            query = {"keyword": "AI", "channels": [channel], "limit": 1}
            result = api_client.search(query)
            sniffer_result_id = result["results"][0]["result_id"]

            save_data = {"kb_id": kb_id, "sniffer_result_id": sniffer_result_id}
            response = api_client.session.post(
                f"{api_client.base_url}/sniffer/save-to-kb",
                json=save_data
            )
            resource_id = response.json()["resource_id"]
            resource_ids.append(resource_id)

            # Verify channel in provenance
            resource = kb_client.get_resource(resource_id)
            assert resource["provenance"]["channel"] == channel

        # Verify all resources in KB
        kb_items = kb_client.list_kb_items(kb_id)
        kb_resource_ids = [item["resource_id"] for item in kb_items]
        for rid in resource_ids:
            assert rid in kb_resource_ids


class TestCrossSystemDataFlow:
    """Test resource lifecycle across multiple systems."""

    def test_resource_lifecycle_across_systems(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test complete resource lifecycle: Source → Tag → KB."""
        # 1. Source → Resource
        source_data = {
            "name": "test-source-lifecycle",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        resources = api_client.list_resources(limit=1)
        assert len(resources) > 0
        resource_id = resources[0]["resource_id"]

        # 2. Tagging → Resource has Tags
        tag = api_client.create_tag("test-lifecycle-tag", weight=1)
        tag_id = tag["tag_id"]
        initial_weight = get_tag_weight(api_client, tag_id)
        api_client.tag_resource(resource_id, tag_id)

        # 3. KB → Tags weight increases
        kb = kb_client.create_kb({"name": "test-kb-lifecycle", "description": "Test"})
        kb_client.add_resource_to_kb(kb["kb_id"], resource_id)
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 1)

        # Verify resource visible in all systems
        assert api_client.list_resources(limit=10)
        assert kb_client.list_kb_items(kb["kb_id"])

    def test_resource_shared_across_multiple_kbs(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that a resource can be shared across multiple KBs."""
        # Create resource with 2 tags
        tag1 = api_client.create_tag("test-shared-tag-1", weight=1)
        tag2 = api_client.create_tag("test-shared-tag-2", weight=1)
        tag1_id = tag1["tag_id"]
        tag2_id = tag2["tag_id"]

        initial_weight1 = get_tag_weight(api_client, tag1_id)
        initial_weight2 = get_tag_weight(api_client, tag2_id)

        source_data = {
            "name": "test-source-shared",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        resources = api_client.list_resources(limit=1)
        resource_id = resources[0]["resource_id"]

        api_client.tag_resource(resource_id, tag1_id)
        api_client.tag_resource(resource_id, tag2_id)

        # Add to 3 different KBs
        kb_ids = []
        for i in range(3):
            kb = kb_client.create_kb({"name": f"test-kb-shared-{i}", "description": f"KB {i}"})
            kb_ids.append(kb["kb_id"])
            kb_client.add_resource_to_kb(kb["kb_id"], resource_id)

        # Verify tag weights accumulated (+3 each)
        verify_tag_weight_increased(api_client, tag1_id, initial_weight1, 3)
        verify_tag_weight_increased(api_client, tag2_id, initial_weight2, 3)

        # Verify resource in all 3 KBs
        for kb_id in kb_ids:
            kb_items = kb_client.list_kb_items(kb_id)
            resource_ids = [item["resource_id"] for item in kb_items]
            assert resource_id in resource_ids

    def test_tag_propagation_through_systems(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test that tags propagate correctly through all systems."""
        # Create resource and tag
        tag = api_client.create_tag("test-propagation-tag", weight=1)
        tag_id = tag["tag_id"]
        initial_weight = get_tag_weight(api_client, tag_id)

        source_data = {
            "name": "test-source-propagation",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        api_client.run_source(source["source_id"])
        time.sleep(1)

        resources = api_client.list_resources(limit=1)
        resource_id = resources[0]["resource_id"]
        api_client.tag_resource(resource_id, tag_id)

        # Add to KB → weight +1
        kb1 = kb_client.create_kb({"name": "test-kb-prop-1", "description": "Test"})
        kb_client.add_resource_to_kb(kb1["kb_id"], resource_id)
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 1)

        # Add to another KB → weight +2
        kb2 = kb_client.create_kb({"name": "test-kb-prop-2", "description": "Test"})
        kb_client.add_resource_to_kb(kb2["kb_id"], resource_id)
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 2)

        # Verify feedback loop works
        final_weight = get_tag_weight(api_client, tag_id)
        assert final_weight == initial_weight + 2


class TestE2EIntegrationWorkflows:
    """Test complete end-to-end user workflows."""

    def test_complete_user_workflow_source_to_kb(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test complete workflow: Create source → Run → Tag → KB."""
        # 1. Create RSS Source
        source_data = {
            "name": "test-workflow-source",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "enabled": True
        }
        source = api_client.create_source(source_data)
        source_id = source["source_id"]
        assert source_id

        # 2. Run Source → Collect Resources
        run_result = api_client.run_source(source_id)
        assert run_result
        time.sleep(1)

        resources = api_client.list_resources(limit=2)
        assert len(resources) > 0
        resource_id = resources[0]["resource_id"]

        # 3. Manual tagging
        tag = api_client.create_tag("test-workflow-tag", weight=1)
        tag_id = tag["tag_id"]
        initial_weight = get_tag_weight(api_client, tag_id)
        api_client.tag_resource(resource_id, tag_id)

        # 4. Create KB
        kb = kb_client.create_kb({"name": "test-workflow-kb", "description": "Workflow test"})
        kb_id = kb["kb_id"]

        # 5. Add resource to KB → Weight boost
        kb_client.add_resource_to_kb(kb_id, resource_id)
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 1)

        # 6. Verify KB contains resource
        kb_items = kb_client.list_kb_items(kb_id)
        resource_ids = [item["resource_id"] for item in kb_items]
        assert resource_id in resource_ids

        # Verify end-to-end flow completed without errors
        assert get_tag_weight(api_client, tag_id) > initial_weight

    @pytest.mark.skip(reason="Requires external sniffer service")
    def test_complete_user_workflow_sniffer_to_kb(
        self,
        api_client: NewsAPIClient,
        kb_client: KBAPIClient,
        integration_cleanup
    ):
        """Test complete workflow: Sniffer → Save to KB → Tag → Weight boost."""
        # 1. Execute Sniffer search
        query = {"keyword": "deep learning", "channels": ["arxiv"], "limit": 1}
        result = api_client.search(query)
        assert len(result["results"]) > 0
        sniffer_result_id = result["results"][0]["result_id"]

        # 2. Save result to KB → Create Resource
        kb = kb_client.create_kb({"name": "test-workflow-sniffer-kb", "description": "Test"})
        kb_id = kb["kb_id"]

        save_data = {"kb_id": kb_id, "sniffer_result_id": sniffer_result_id}
        response = api_client.session.post(
            f"{api_client.base_url}/sniffer/save-to-kb",
            json=save_data
        )
        response.raise_for_status()
        resource_id = response.json()["resource_id"]

        # 3. Manual tagging → Tag association
        tag = api_client.create_tag("test-sniffer-workflow-tag", weight=1)
        tag_id = tag["tag_id"]
        initial_weight = get_tag_weight(api_client, tag_id)
        api_client.tag_resource(resource_id, tag_id)

        # 4. Add to another KB → Weight boost
        kb2 = kb_client.create_kb({"name": "test-workflow-sniffer-kb-2", "description": "Test"})
        kb_client.add_resource_to_kb(kb2["kb_id"], resource_id)
        verify_tag_weight_increased(api_client, tag_id, initial_weight, 1)

        # 5. Verify provenance chain complete
        verify_provenance_chain(kb_client, resource_id, "sniffer:arxiv")

        # Verify tag weight feedback normal
        final_weight = get_tag_weight(api_client, tag_id)
        assert final_weight > initial_weight
