from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from core.agent.base import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class InferredLink:
    node_a_id: str
    node_b_id: str
    reason: str


class KGLinkEngine:
    """LLM-based engine for inferring semantic connections between KB nodes."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def infer_links(
        self,
        new_node: dict,
        candidates: list[dict],
        blocked_pairs: set[tuple[str, str]],
        max_links: int = 5,
    ) -> list[InferredLink]:
        """
        Use LLM to infer semantic connections between new_node and candidates.

        Args:
            new_node: The newly added node (dict with id, title, summary)
            candidates: List of candidate nodes to consider
            blocked_pairs: Set of (a, b) pairs that user has explicitly deleted
            max_links: Maximum number of links to return

        Returns:
            List of InferredLink objects
        """
        if not candidates:
            return []

        # Filter out blocked pairs
        new_id = new_node["id"]
        valid_candidates = []
        for c in candidates:
            pair = tuple(sorted([new_id, c["id"]]))
            if pair not in blocked_pairs:
                valid_candidates.append(c)

        if not valid_candidates:
            return []

        # Build prompt
        prompt = self._build_prompt(new_node, valid_candidates, max_links)

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )

            # Parse JSON response
            links = self._parse_response(response.content, new_id)
            logger.info(f"[KGLinkEngine] Inferred {len(links)} links for node {new_id}")
            return links[:max_links]

        except Exception as exc:
            logger.error(f"[KGLinkEngine] Failed to infer links: {exc}")
            return []

    def _build_prompt(self, new_node: dict, candidates: list[dict], max_links: int) -> str:
        """Build the LLM prompt for link inference."""
        candidates_text = "\n\n".join([
            f"ID: {c['id']}\nTitle: {c['title']}\nSummary: {c.get('summary', 'N/A')}"
            for c in candidates
        ])

        return f"""You are a knowledge graph expert. A new resource has been added to a knowledge base.

NEW RESOURCE:
ID: {new_node['id']}
Title: {new_node['title']}
Summary: {new_node.get('summary', 'N/A')}

EXISTING RESOURCES:
{candidates_text}

Task: Identify up to {max_links} semantic connections between the new resource and existing resources.
A connection should exist if:
- They discuss related topics or concepts
- One builds upon or references the other
- They provide complementary perspectives
- They share significant thematic overlap

For each connection, provide:
1. The ID of the existing resource
2. A concise reason (1-2 sentences) explaining the connection

Output format (JSON array):
[
  {{"target_id": "resource_id", "reason": "Brief explanation"}},
  ...
]

If no meaningful connections exist, return an empty array: []

Output only the JSON array, no additional text."""

    def _parse_response(self, content: str, new_node_id: str) -> list[InferredLink]:
        """Parse LLM response into InferredLink objects."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            data = json.loads(content)

            if not isinstance(data, list):
                logger.warning("[KGLinkEngine] Response is not a list")
                return []

            links = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                target_id = item.get("target_id")
                reason = item.get("reason")
                if target_id and reason:
                    links.append(InferredLink(
                        node_a_id=new_node_id,
                        node_b_id=target_id,
                        reason=reason,
                    ))

            return links

        except json.JSONDecodeError as exc:
            logger.error(f"[KGLinkEngine] Failed to parse JSON: {exc}")
            return []
