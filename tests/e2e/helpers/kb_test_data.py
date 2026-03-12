"""Test data generators for KB system E2E tests."""
import random
import string


def generate_random_suffix(length: int = 6) -> str:
    """Generate random string suffix for unique test names."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_test_kb(name: str = None, description: str = None) -> dict:
    """Generate test knowledge base data."""
    if name is None:
        name = f"test-kb-{generate_random_suffix()}"

    if description is None:
        description = f"Test KB for E2E testing - {generate_random_suffix()}"

    return {
        "name": name,
        "description": description
    }


def generate_test_graph_edge(
    node_a_id: str,
    node_b_id: str,
    reason: str = None,
    reason_type: str = "manual"
) -> dict:
    """Generate test graph edge data."""
    if reason is None:
        reason = f"Test relationship - {generate_random_suffix()}"

    return {
        "node_a_id": node_a_id,
        "node_b_id": node_b_id,
        "reason": reason,
        "reason_type": reason_type
    }
