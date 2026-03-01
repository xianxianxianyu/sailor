"""S3 smoke tests — ResourceIntelligenceEngine."""
import json
import uuid

from core.models import Job, Resource, ResourceAnalysis
from core.engines.intelligence import ResourceIntelligenceEngine


class FakeTaggingAgent:
    def __init__(self, tag_repo):
        self.tag_repo = tag_repo

    def tag_resource(self, resource_id, title, text):
        tag = self.tag_repo.create_tag("AI")
        self.tag_repo.tag_resource(resource_id, tag.tag_id, source="test")
        return ["AI"]


class FakeArticleAgent:
    def __init__(self, analysis_repo):
        self.analysis_repo = analysis_repo

    def analyze(self, resource):
        analysis = ResourceAnalysis(
            resource_id=resource.resource_id,
            summary="Test summary",
            topics_json='["AI"]',
            scores_json="{}",
            kb_recommendations_json="[]",
            insights_json="{}",
            model="fake",
            status="completed",
        )
        self.analysis_repo.save(analysis)
        return analysis


def _insert_resource(resource_repo, rid="res_intel00001"):
    resource_repo.upsert(Resource(
        resource_id=rid,
        canonical_url=f"https://example.com/{rid}",
        source="test",
        provenance={},
        title="Intelligence Test",
        published_at=None,
        text="Content about AI and machine learning.",
        original_url=f"https://example.com/{rid}",
        topics=["General"],
        summary="Test",
    ))
    return rid


def test_engine_processes_resources(resource_repo, tag_repo, analysis_repo):
    rid = _insert_resource(resource_repo)
    engine = ResourceIntelligenceEngine(
        resource_repo=resource_repo,
        tag_repo=tag_repo,
        analysis_repo=analysis_repo,
        tagging_agent=FakeTaggingAgent(tag_repo),
        article_agent=FakeArticleAgent(analysis_repo),
    )
    results = engine.process([rid])
    assert len(results) == 1
    assert results[0].tags == ["AI"]
    assert results[0].analysis_status == "completed"


def test_engine_idempotent(resource_repo, tag_repo, analysis_repo):
    rid = _insert_resource(resource_repo)
    engine = ResourceIntelligenceEngine(
        resource_repo=resource_repo,
        tag_repo=tag_repo,
        analysis_repo=analysis_repo,
        tagging_agent=FakeTaggingAgent(tag_repo),
        article_agent=FakeArticleAgent(analysis_repo),
    )
    results1 = engine.process([rid])
    results2 = engine.process([rid])
    # Second run should reuse existing tags and analysis
    assert results2[0].tags == ["AI"]
    assert results2[0].analysis_status == "completed"
