"""API client for KB (Knowledge Base) system E2E tests."""
import requests
from typing import Optional


class KBAPIClient:
    """Client for interacting with Sailor KB APIs."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    # Knowledge Bases
    def create_kb(self, data_or_name, description: str = None) -> dict:
        """Create a new knowledge base.

        Args:
            data_or_name: Either a dict with 'name' and 'description', or a string name
            description: Optional description (only used if data_or_name is a string)
        """
        if isinstance(data_or_name, dict):
            data = data_or_name
        else:
            data = {"name": data_or_name}
            if description:
                data["description"] = description

        response = self.session.post(f"{self.base_url}/knowledge-bases", json=data)
        response.raise_for_status()
        return response.json()

    def list_kbs(self) -> list[dict]:
        """List all knowledge bases."""
        response = self.session.get(f"{self.base_url}/knowledge-bases")
        response.raise_for_status()
        return response.json()

    def delete_kb(self, kb_id: str) -> None:
        """Delete a knowledge base."""
        response = self.session.delete(f"{self.base_url}/knowledge-bases/{kb_id}")
        response.raise_for_status()

    # KB Items
    def add_item_to_kb(self, kb_id: str, resource_id: str) -> dict:
        """Add a resource to a knowledge base."""
        data = {"resource_id": resource_id}
        response = self.session.post(
            f"{self.base_url}/knowledge-bases/{kb_id}/items", json=data
        )
        response.raise_for_status()
        return response.json()

    def list_kb_items(self, kb_id: str) -> list[dict]:
        """List all items in a knowledge base."""
        response = self.session.get(f"{self.base_url}/knowledge-bases/{kb_id}/items")
        response.raise_for_status()
        return response.json()

    def remove_item_from_kb(self, kb_id: str, resource_id: str) -> None:
        """Remove a resource from a knowledge base."""
        response = self.session.delete(
            f"{self.base_url}/knowledge-bases/{kb_id}/items/{resource_id}"
        )
        response.raise_for_status()

    # Resources
    def list_resources(
        self, topic: Optional[str] = None, inbox_only: bool = False, limit: int = 10
    ) -> list[dict]:
        """List resources with optional filters."""
        params = {"limit": limit}
        if topic:
            params["topic"] = topic
        if inbox_only:
            params["inbox_only"] = "true"
        response = self.session.get(f"{self.base_url}/resources", params=params)
        response.raise_for_status()
        return response.json()

    def get_resource(self, resource_id: str) -> dict:
        """Get a single resource."""
        response = self.session.get(f"{self.base_url}/resources/{resource_id}")
        response.raise_for_status()
        return response.json()

    def get_resource_kbs(self, resource_id: str) -> list[dict]:
        """Get all KBs containing a resource."""
        response = self.session.get(
            f"{self.base_url}/resources/{resource_id}/knowledge-bases"
        )
        response.raise_for_status()
        return response.json()

    # Resource Analysis
    def analyze_resource(self, resource_id: str) -> dict:
        """Analyze a resource with LLM."""
        response = self.session.post(f"{self.base_url}/resources/{resource_id}/analyze")
        response.raise_for_status()
        return response.json()

    def get_resource_analysis(self, resource_id: str) -> dict:
        """Get analysis result for a resource."""
        response = self.session.get(f"{self.base_url}/resources/{resource_id}/analysis")
        response.raise_for_status()
        return response.json()

    def batch_analyze(self, resource_ids: list[str] = None) -> dict:
        """Batch analyze resources."""
        data = {}
        if resource_ids:
            data["resource_ids"] = resource_ids
        response = self.session.post(f"{self.base_url}/tasks/run-analysis", json=data)
        response.raise_for_status()
        return response.json()

    def get_analysis_status(self) -> dict:
        """Get analysis status summary."""
        response = self.session.get(f"{self.base_url}/analyses/status")
        response.raise_for_status()
        return response.json()

    # KB Reports
    def generate_kb_reports(self, kb_id: str) -> list[dict]:
        """Generate all report types for a KB."""
        response = self.session.post(
            f"{self.base_url}/knowledge-bases/{kb_id}/reports"
        )
        response.raise_for_status()
        return response.json()

    def list_kb_reports(self, kb_id: str) -> list[dict]:
        """List all reports for a KB."""
        response = self.session.get(f"{self.base_url}/knowledge-bases/{kb_id}/reports")
        response.raise_for_status()
        return response.json()

    def get_latest_kb_report(self, kb_id: str, report_type: str = None) -> dict:
        """Get latest report for a KB by type."""
        params = {}
        if report_type:
            params["report_type"] = report_type
        response = self.session.get(
            f"{self.base_url}/knowledge-bases/{kb_id}/reports/latest", params=params
        )
        response.raise_for_status()
        return response.json()

    # KB Graph
    def get_kb_graph(self, kb_id: str) -> dict:
        """Get full knowledge graph for a KB."""
        response = self.session.get(f"{self.base_url}/knowledge-bases/{kb_id}/graph")
        response.raise_for_status()
        return response.json()

    def get_graph_node(self, kb_id: str, node_id: str) -> dict:
        """Get a graph node with its neighbors."""
        response = self.session.get(
            f"{self.base_url}/knowledge-bases/{kb_id}/graph/nodes/{node_id}"
        )
        response.raise_for_status()
        return response.json()

    def create_graph_edge(
        self,
        kb_id: str,
        node_a_id: str,
        node_b_id: str,
        reason: str,
        reason_type: str = "manual",
    ) -> dict:
        """Create or update an edge between two nodes."""
        data = {
            "node_a_id": node_a_id,
            "node_b_id": node_b_id,
            "reason": reason,
            "reason_type": reason_type,
        }
        response = self.session.post(
            f"{self.base_url}/knowledge-bases/{kb_id}/graph/edges", json=data
        )
        response.raise_for_status()
        return response.json()

    def delete_graph_edge(self, kb_id: str, node_a_id: str, node_b_id: str) -> None:
        """Soft delete an edge."""
        response = self.session.delete(
            f"{self.base_url}/knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}"
        )
        response.raise_for_status()

    def freeze_graph_edge(self, kb_id: str, node_a_id: str, node_b_id: str) -> dict:
        """Freeze an edge to prevent AI updates."""
        response = self.session.post(
            f"{self.base_url}/knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/freeze"
        )
        response.raise_for_status()
        return response.json()

    def unfreeze_graph_edge(self, kb_id: str, node_a_id: str, node_b_id: str) -> dict:
        """Unfreeze an edge."""
        response = self.session.post(
            f"{self.base_url}/knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/unfreeze"
        )
        response.raise_for_status()
        return response.json()

    # Health check
    def healthz(self) -> dict:
        """Check service health."""
        response = self.session.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()
