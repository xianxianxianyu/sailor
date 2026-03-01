"""S2 smoke tests — trending pipeline orchestration."""
import json
import uuid

from core.models import Job, Resource
from core.runner.job_runner import JobRunner
from core.runner.tagging_handler import TaggingHandler
from core.runner.trending_handler import TrendingHandler


class FakeTaggingAgent:
    def __init__(self, tag_repo):
        self.tag_repo = tag_repo

    def tag_resource(self, resource_id, title, text):
        tag = self.tag_repo.create_tag("TestTag")
        self.tag_repo.tag_resource(resource_id, tag.tag_id, source="test")
        return ["TestTag"]


def _insert_resource(resource_repo, rid="res_test000001"):
    resource_repo.upsert(Resource(
        resource_id=rid,
        canonical_url=f"https://example.com/{rid}",
        source="test",
        provenance={},
        title="Test Article",
        published_at=None,
        text="Some interesting content about LLM and AI.",
        original_url=f"https://example.com/{rid}",
        topics=["General"],
        summary="Test summary",
    ))


def test_tagging_handler(job_repo, resource_repo, tag_repo):
    _insert_resource(resource_repo)
    agent = FakeTaggingAgent(tag_repo)
    handler = TaggingHandler(agent, resource_repo, tag_repo)

    job = job_repo.create_job(Job(
        job_id=uuid.uuid4().hex[:12],
        job_type="batch_tag",
        input_json="{}",
    ))
    from core.runner.handlers import RunContext
    ctx = RunContext(job_repo=job_repo, run_id=job.job_id)
    output = handler.execute(job, ctx)

    result = json.loads(output)
    assert result["tagged"] >= 1
    assert result["failed"] == 0


def test_trending_handler(job_repo, resource_repo, tag_repo):
    _insert_resource(resource_repo)
    handler = TrendingHandler(resource_repo, tag_repo)

    job = job_repo.create_job(Job(
        job_id=uuid.uuid4().hex[:12],
        job_type="trending_generate",
        input_json="{}",
    ))
    from core.runner.handlers import RunContext
    ctx = RunContext(job_repo=job_repo, run_id=job.job_id)
    output = handler.execute(job, ctx)

    result = json.loads(output)
    assert "total_resources" in result
    assert result["total_resources"] >= 1
