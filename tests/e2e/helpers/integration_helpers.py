"""Helper functions for cross-system integration tests."""
import time
from typing import Optional
from .api_client import NewsAPIClient
from .kb_api_client import KBAPIClient


def get_tag_weight(api_client: NewsAPIClient, tag_id: str) -> int:
    """Get current tag weight."""
    tag = api_client.get_tag(tag_id)
    return tag["weight"]


def verify_tag_weight_increased(
    api_client: NewsAPIClient,
    tag_id: str,
    initial_weight: int,
    expected_increase: int
) -> None:
    """Verify that tag weight has increased by expected amount."""
    current = get_tag_weight(api_client, tag_id)
    assert current == initial_weight + expected_increase, (
        f"Expected weight {initial_weight + expected_increase}, got {current}"
    )


def create_test_resource_with_tags(
    api_client: NewsAPIClient,
    num_tags: int = 2,
    source_name: str = "test-integration-source"
) -> tuple[str, list[str]]:
    """Create a test resource with tags.

    Returns:
        tuple: (resource_id, [tag_ids])
    """
    # Create source
    source_data = {
        "name": source_name,
        "source_type": "rss",
        "url": "https://example.com/feed.xml",
        "enabled": True
    }
    source = api_client.create_source(source_data)
    source_id = source["source_id"]

    # Run source to get resources
    api_client.run_source(source_id)
    time.sleep(1)  # Brief wait for resource creation

    # Get resources
    resources = api_client.list_resources(limit=1)
    if not resources:
        raise RuntimeError("No resources created from source")

    resource_id = resources[0]["resource_id"]

    # Create tags and tag the resource
    tag_ids = []
    for i in range(num_tags):
        tag = api_client.create_tag(f"test-tag-{i}-{int(time.time())}")
        tag_id = tag["tag_id"]
        tag_ids.append(tag_id)
        api_client.tag_resource(resource_id, tag_id)

    return resource_id, tag_ids


def verify_provenance_chain(
    kb_client: KBAPIClient,
    resource_id: str,
    expected_source: str
) -> None:
    """Verify that provenance chain is complete."""
    resource = kb_client.get_resource(resource_id)

    assert resource["source"] == expected_source, (
        f"Expected source '{expected_source}', got '{resource['source']}'"
    )
    assert "provenance" in resource, "Resource missing provenance field"
    assert resource["provenance"], "Provenance is empty"


def wait_for_resources(
    api_client: NewsAPIClient,
    min_count: int = 1,
    timeout: int = 10
) -> list[dict]:
    """Wait for resources to be created."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        resources = api_client.list_resources(limit=min_count * 2)
        if len(resources) >= min_count:
            return resources
        time.sleep(1)

    raise TimeoutError(f"Timeout waiting for {min_count} resources")


def create_kb_with_resource(
    kb_client: KBAPIClient,
    resource_id: str,
    kb_name: Optional[str] = None
) -> str:
    """Create a KB and add a resource to it.

    Returns:
        str: kb_id
    """
    if kb_name is None:
        kb_name = f"test-kb-{int(time.time())}"

    # Create KB
    kb_data = {
        "name": kb_name,
        "description": "Test KB for integration tests"
    }
    kb = kb_client.create_kb(kb_data)
    kb_id = kb["kb_id"]

    # Add resource to KB
    kb_client.add_resource_to_kb(kb_id, resource_id)

    return kb_id
