"""API client for News system E2E tests."""
import requests
from typing import Optional


class NewsAPIClient:
    """Client for interacting with Sailor News APIs."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    # Sources
    def create_source(self, data: dict) -> dict:
        """Create a new source."""
        response = self.session.post(f"{self.base_url}/sources", json=data)
        response.raise_for_status()
        return response.json()

    def run_source(self, source_id: str) -> dict:
        """Trigger source run."""
        response = self.session.post(f"{self.base_url}/sources/{source_id}/run")
        response.raise_for_status()
        return response.json()

    def list_sources(self) -> list[dict]:
        """List all sources."""
        response = self.session.get(f"{self.base_url}/sources")
        response.raise_for_status()
        return response.json()

    def get_source(self, source_id: str) -> dict:
        """Get source by ID."""
        response = self.session.get(f"{self.base_url}/sources/{source_id}")
        response.raise_for_status()
        return response.json()

    def delete_source(self, source_id: str) -> None:
        """Delete a source."""
        response = self.session.delete(f"{self.base_url}/sources/{source_id}")
        response.raise_for_status()

    # Paper Sources
    def create_paper_source(self, data: dict) -> dict:
        """Create a new paper source."""
        response = self.session.post(f"{self.base_url}/paper-sources", json=data)
        response.raise_for_status()
        return response.json()

    def run_paper_source(self, source_id: str) -> dict:
        """Trigger paper source run."""
        response = self.session.post(f"{self.base_url}/paper-sources/{source_id}/run")
        response.raise_for_status()
        return response.json()

    def list_paper_sources(self) -> list[dict]:
        """List all paper sources."""
        response = self.session.get(f"{self.base_url}/paper-sources")
        response.raise_for_status()
        return response.json()

    def list_papers(self, limit: int = 10) -> list[dict]:
        """List papers."""
        response = self.session.get(f"{self.base_url}/papers", params={"limit": limit})
        response.raise_for_status()
        return response.json()

    def delete_paper_source(self, source_id: str) -> None:
        """Delete a paper source."""
        response = self.session.delete(f"{self.base_url}/paper-sources/{source_id}")
        response.raise_for_status()

    # Tags
    def create_tag(self, name: str, color: str = "#0f766e", weight: int = 1) -> dict:
        """Create a new tag."""
        data = {"name": name, "color": color, "weight": weight}
        response = self.session.post(f"{self.base_url}/tags", json=data)
        response.raise_for_status()
        return response.json()

    def tag_resource(self, resource_id: str, tag_id: str) -> None:
        """Tag a resource."""
        data = {"resource_id": resource_id, "tag_id": tag_id}
        response = self.session.post(f"{self.base_url}/tags/tag-resource", json=data)
        response.raise_for_status()

    def list_tags(self) -> list[dict]:
        """List all tags."""
        response = self.session.get(f"{self.base_url}/tags")
        response.raise_for_status()
        return response.json()

    def delete_tag(self, tag_id: str) -> None:
        """Delete a tag."""
        response = self.session.delete(f"{self.base_url}/tags/{tag_id}")
        response.raise_for_status()

    def get_tag(self, tag_id: str) -> dict:
        """Get a single tag by ID."""
        response = self.session.get(f"{self.base_url}/tags/{tag_id}")
        response.raise_for_status()
        return response.json()

    def list_user_actions(self, limit: int = 10) -> list[dict]:
        """List recent user actions."""
        response = self.session.get(f"{self.base_url}/actions", params={"limit": limit})
        response.raise_for_status()
        return response.json()

    # Resources
    def list_resources(self, tag_id: Optional[str] = None, limit: int = 10) -> list[dict]:
        """List resources, optionally filtered by tag."""
        params = {"limit": limit}
        if tag_id:
            params["tag_id"] = tag_id
        response = self.session.get(f"{self.base_url}/resources", params=params)
        response.raise_for_status()
        return response.json()

    # Sniffer
    def search(self, query: dict) -> dict:
        """Execute sniffer search."""
        response = self.session.post(f"{self.base_url}/sniffer/search", json=query)
        response.raise_for_status()
        return response.json()

    def create_pack(self, data: dict) -> dict:
        """Create a sniffer pack."""
        response = self.session.post(f"{self.base_url}/sniffer/packs", json=data)
        response.raise_for_status()
        return response.json()

    def run_pack(self, pack_id: str) -> dict:
        """Run a sniffer pack."""
        response = self.session.post(f"{self.base_url}/sniffer/packs/{pack_id}/run")
        response.raise_for_status()
        return response.json()

    def list_packs(self) -> list[dict]:
        """List all sniffer packs."""
        response = self.session.get(f"{self.base_url}/sniffer/packs")
        response.raise_for_status()
        return response.json()

    def delete_pack(self, pack_id: str) -> None:
        """Delete a sniffer pack."""
        response = self.session.delete(f"{self.base_url}/sniffer/packs/{pack_id}")
        response.raise_for_status()

    # Health check
    def healthz(self) -> dict:
        """Check service health."""
        response = self.session.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()
