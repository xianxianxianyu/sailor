"""Test data generators for E2E tests."""
import random
import string
from datetime import datetime


def generate_random_suffix(length: int = 6) -> str:
    """Generate random string suffix for unique test names."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_test_source(name: str = None, source_type: str = "rss") -> dict:
    """Generate test source data."""
    if name is None:
        name = f"test-source-{generate_random_suffix()}"

    return {
        "source_type": source_type,
        "name": name,
        "endpoint": "https://hnrss.org/newest?count=5",  # HN RSS feed (reliable)
        "enabled": True,
        "schedule_minutes": 60,
        "config": {}
    }


def generate_test_paper_source(name: str = None, provider: str = "arxiv") -> dict:
    """Generate test paper source data."""
    if name is None:
        name = f"test-paper-{generate_random_suffix()}"

    return {
        "name": name,
        "platform": provider,  # Changed from 'provider' to 'platform'
        "endpoint": "https://export.arxiv.org/api/query",  # Added endpoint
        "enabled": True,
        "schedule_minutes": 1440,  # Daily
        "config": {
            "query": "cat:cs.AI",  # Moved query to config
            "max_results": 5
        }
    }


def generate_test_tag(name: str = None, color: str = "#0f766e") -> dict:
    """Generate test tag data."""
    if name is None:
        name = f"test-tag-{generate_random_suffix()}"

    return {
        "name": name,
        "color": color,
        "weight": 1
    }


def generate_test_sniffer_query(keyword: str = "python", channels: list[str] = None) -> dict:
    """Generate test sniffer query."""
    if channels is None:
        channels = ["github", "hackernews"]

    return {
        "keyword": keyword,
        "channels": channels,
        "limit": 5
    }


def generate_test_pack(name: str = None, keyword: str = "AI", channels: list[str] = None) -> dict:
    """Generate test sniffer pack data."""
    if name is None:
        name = f"test-pack-{generate_random_suffix()}"

    if channels is None:
        channels = ["github", "hackernews"]

    return {
        "name": name,
        "query": {
            "keyword": keyword,
            "channels": channels,
            "time_range": "all",
            "sort_by": "relevance",
            "max_results_per_channel": 10
        },
        "description": f"Test pack for {keyword}"
    }
