"""Pytest configuration and fixtures for E2E tests."""
import pytest
import time
from typing import Generator
from .helpers.api_client import NewsAPIClient
from .helpers.kb_api_client import KBAPIClient


# Configuration
BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30


@pytest.fixture(scope="session")
def api_client() -> NewsAPIClient:
    """Provide API client for tests."""
    client = NewsAPIClient(base_url=BASE_URL)

    # Verify service is running
    try:
        client.healthz()
    except Exception as e:
        pytest.skip(f"Service not available at {BASE_URL}: {e}")

    return client


@pytest.fixture(scope="session")
def kb_client() -> KBAPIClient:
    """Provide KB API client for tests."""
    client = KBAPIClient(base_url=BASE_URL)

    # Verify service is running
    try:
        client.healthz()
    except Exception as e:
        pytest.skip(f"Service not available at {BASE_URL}: {e}")

    return client


@pytest.fixture(scope="function")
def cleanup_test_sources(api_client: NewsAPIClient) -> Generator[None, None, None]:
    """Clean up test sources after test."""
    yield

    try:
        sources = api_client.list_sources()
        for source in sources:
            if source.get("name", "").startswith("test-"):
                try:
                    api_client.delete_source(source["source_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup source {source['source_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list sources for cleanup: {e}")


@pytest.fixture(scope="function")
def cleanup_test_paper_sources(api_client: NewsAPIClient) -> Generator[None, None, None]:
    """Clean up test paper sources after test."""
    yield

    try:
        sources = api_client.list_paper_sources()
        for source in sources:
            if source.get("name", "").startswith("test-"):
                try:
                    api_client.delete_paper_source(source["source_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup paper source {source['source_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list paper sources for cleanup: {e}")


@pytest.fixture(scope="function")
def cleanup_test_tags(api_client: NewsAPIClient) -> Generator[None, None, None]:
    """Clean up test tags after test."""
    yield

    try:
        tags = api_client.list_tags()
        for tag in tags:
            if tag.get("name", "").startswith("test-"):
                try:
                    api_client.delete_tag(tag["tag_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup tag {tag['tag_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list tags for cleanup: {e}")


@pytest.fixture(scope="function")
def cleanup_test_packs(api_client: NewsAPIClient) -> Generator[None, None, None]:
    """Clean up test sniffer packs after test."""
    yield

    try:
        packs = api_client.list_packs()
        for pack in packs:
            if pack.get("name", "").startswith("test-"):
                try:
                    api_client.delete_pack(pack["pack_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup pack {pack['pack_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list packs for cleanup: {e}")


@pytest.fixture(scope="function")
def cleanup_test_kbs(kb_client: KBAPIClient) -> Generator[None, None, None]:
    """Clean up test knowledge bases after test."""
    yield

    try:
        kbs = kb_client.list_kbs()
        for kb in kbs:
            if kb.get("name", "").startswith("test-"):
                try:
                    kb_client.delete_kb(kb["kb_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup KB {kb['kb_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list KBs for cleanup: {e}")


@pytest.fixture(scope="function")
def integration_cleanup(
    api_client: NewsAPIClient,
    kb_client: KBAPIClient
) -> Generator[None, None, None]:
    """Comprehensive cleanup fixture for integration tests."""
    yield

    # Cleanup order: KB items → KBs → Tags → Sources
    try:
        # Clean KBs
        kbs = kb_client.list_kbs()
        for kb in kbs:
            if kb.get("name", "").startswith("test-"):
                try:
                    kb_client.delete_kb(kb["kb_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup KB {kb['kb_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list KBs for cleanup: {e}")

    try:
        # Clean tags
        tags = api_client.list_tags()
        for tag in tags:
            if tag.get("name", "").startswith("test-"):
                try:
                    api_client.delete_tag(tag["tag_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup tag {tag['tag_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list tags for cleanup: {e}")

    try:
        # Clean sources
        sources = api_client.list_sources()
        for source in sources:
            if source.get("name", "").startswith("test-"):
                try:
                    api_client.delete_source(source["source_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup source {source['source_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list sources for cleanup: {e}")

    try:
        # Clean packs
        packs = api_client.list_packs()
        for pack in packs:
            if pack.get("name", "").startswith("test-"):
                try:
                    api_client.delete_pack(pack["pack_id"])
                except Exception as e:
                    print(f"Warning: Failed to cleanup pack {pack['pack_id']}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list packs for cleanup: {e}")


def wait_for_condition(condition_fn, timeout: int = DEFAULT_TIMEOUT, interval: float = 1.0) -> bool:
    """Wait for a condition to become true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_fn():
            return True
        time.sleep(interval)
    return False
