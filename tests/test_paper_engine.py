"""Paper Engine Unit Tests

测试 PaperRepository 的 CRUD 操作和幂等性
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core.paper import PaperRepository
from core.paper.models import PaperRecord
from core.storage import Database


@pytest.fixture
def paper_repo(tmp_path: Path) -> PaperRepository:
    """创建临时 PaperRepository"""
    db_path = tmp_path / "test_paper.db"
    db = Database(db_path)
    db.init_schema()
    return PaperRepository(db)


# ========== Module 1: Paper Source Registry ==========


def test_create_paper_source(paper_repo: PaperRepository):
    """测试创建 paper source"""
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="arXiv AI Papers",
        config_json=json.dumps({"max_results": 100}),
    )

    assert source.source_id.startswith("paper_arxiv_")
    assert source.platform == "arxiv"
    assert source.endpoint == "cat:cs.AI"
    assert source.name == "arXiv AI Papers"
    assert source.enabled is True


def test_source_id_deterministic(paper_repo: PaperRepository):
    """测试 source_id 生成的确定性"""
    source1 = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Name 1",
        config_json="{}",
    )

    source2 = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Name 2",  # 不同的 name
        config_json="{}",
    )

    # 相同的 platform + endpoint 应该生成相同的 source_id
    assert source1.source_id == source2.source_id


def test_list_sources_filter(paper_repo: PaperRepository):
    """测试 source 列表过滤"""
    paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="arXiv AI",
        config_json="{}",
        enabled=True,
    )

    paper_repo.upsert_source(
        source_id=None,
        platform="openreview",
        endpoint="ICLR.cc/2024/Conference",
        name="ICLR 2024",
        config_json="{}",
        enabled=False,
    )

    # 所有 sources
    all_sources = paper_repo.list_sources()
    assert len(all_sources) == 2

    # 只看 enabled
    enabled_sources = paper_repo.list_sources(enabled=True)
    assert len(enabled_sources) == 1
    assert enabled_sources[0].platform == "arxiv"

    # 按 platform 过滤
    arxiv_sources = paper_repo.list_sources(platform="arxiv")
    assert len(arxiv_sources) == 1


def test_update_source(paper_repo: PaperRepository):
    """测试更新 source"""
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Original Name",
        config_json="{}",
    )

    # 更新 name 和 cursor
    updated = paper_repo.update_source(
        source.source_id,
        name="Updated Name",
        cursor_json=json.dumps({"start": 100}),
    )

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.cursor_json == json.dumps({"start": 100})


def test_delete_source(paper_repo: PaperRepository):
    """测试删除 source"""
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    success = paper_repo.delete_source(source.source_id)
    assert success is True

    # 验证已删除
    deleted = paper_repo.get_source(source.source_id)
    assert deleted is None


# ========== Module 2: Paper Canonical Store ==========


def test_upsert_paper(paper_repo: PaperRepository):
    """测试 paper upsert"""
    record = PaperRecord(
        canonical_id="arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Test Paper",
        item_key="v1:arxiv:2401.12345",
        abstract="This is a test",
        published_at=datetime(2024, 1, 15),
        authors=["Alice", "Bob"],
        venue="cs.AI",
        doi=None,
        pdf_url="https://arxiv.org/pdf/2401.12345.pdf",
        external_ids={"arxiv_id": "2401.12345"},
    )

    paper_id = paper_repo.upsert_paper(record)
    assert paper_id.startswith("paper_")

    # 读取验证
    paper = paper_repo.get_paper(paper_id)
    assert paper is not None
    assert paper.canonical_id == "arxiv:2401.12345"
    assert paper.title == "Test Paper"
    assert json.loads(paper.authors_json or "[]") == ["Alice", "Bob"]


def test_paper_idempotent_upsert(paper_repo: PaperRepository):
    """测试 paper 幂等 upsert（相同 canonical_id）"""
    record1 = PaperRecord(
        canonical_id="arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Original Title",
        item_key="v1:arxiv:2401.12345",
    )

    paper_id1 = paper_repo.upsert_paper(record1)

    # 再次 upsert，更新 title
    record2 = PaperRecord(
        canonical_id="arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Updated Title",
        item_key="v1:arxiv:2401.12345",
    )

    paper_id2 = paper_repo.upsert_paper(record2)

    # 应该是同一个 paper_id
    assert paper_id1 == paper_id2

    # 验证 title 已更新
    paper = paper_repo.get_paper(paper_id1)
    assert paper is not None
    assert paper.title == "Updated Title"


def test_list_papers(paper_repo: PaperRepository):
    """测试 paper 列表"""
    # 插入多个 papers
    for i in range(5):
        record = PaperRecord(
            canonical_id=f"arxiv:240{i}.12345",
            canonical_url=f"https://arxiv.org/abs/240{i}.12345",
            title=f"Paper {i}",
            item_key=f"v1:arxiv:240{i}.12345",
            published_at=datetime(2024, 1, i + 1),
        )
        paper_repo.upsert_paper(record)

    # 列出所有
    papers = paper_repo.list_papers(limit=10)
    assert len(papers) == 5

    # 验证按 published_at 倒序
    assert papers[0].published_at > papers[-1].published_at


# ========== Module 3: Paper Source Item Index ==========


def test_mark_seen(paper_repo: PaperRepository):
    """测试 mark_seen"""
    # 创建 source 和 paper
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    record = PaperRecord(
        canonical_id="arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Test Paper",
        item_key="v1:arxiv:2401.12345",
    )
    paper_id = paper_repo.upsert_paper(record)

    # 标记已见
    seen_at = datetime.utcnow()
    paper_repo.mark_seen(source.source_id, record.item_key, paper_id, seen_at)

    # 验证
    assert paper_repo.has_seen(source.source_id, record.item_key) is True
    assert paper_repo.has_seen(source.source_id, "v1:arxiv:9999.99999") is False


def test_list_papers_by_source(paper_repo: PaperRepository):
    """测试按 source 列出 papers"""
    # 创建 source
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    # 插入 papers 并标记
    seen_at = datetime.utcnow()
    for i in range(3):
        record = PaperRecord(
            canonical_id=f"arxiv:240{i}.12345",
            canonical_url=f"https://arxiv.org/abs/240{i}.12345",
            title=f"Paper {i}",
            item_key=f"v1:arxiv:240{i}.12345",
        )
        paper_id = paper_repo.upsert_paper(record)
        paper_repo.mark_seen(source.source_id, record.item_key, paper_id, seen_at)

    # 查询
    papers = paper_repo.list_papers_by_source(source.source_id, limit=10)
    assert len(papers) == 3


def test_list_papers_by_sources_and_window_basic(paper_repo: PaperRepository):
    """测试多源查询基本功能"""
    # 创建 2 个 sources
    source1 = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Source 1",
        config_json="{}",
    )
    source2 = paper_repo.upsert_source(
        source_id=None,
        platform="openreview",
        endpoint="ICLR.cc/2024",
        name="Source 2",
        config_json="{}",
    )

    # 创建 3 个 papers
    seen_at = datetime.utcnow()
    papers_data = []
    for i in range(3):
        record = PaperRecord(
            canonical_id=f"paper:240{i}.12345",
            canonical_url=f"https://example.com/240{i}.12345",
            title=f"Paper {i}",
            item_key=f"v1:240{i}.12345",
            published_at=datetime(2024, 1, i + 1),
        )
        paper_id = paper_repo.upsert_paper(record)
        papers_data.append((paper_id, record))

    # Paper 0 在两个 sources 中（测试 DISTINCT）
    paper_repo.mark_seen(source1.source_id, papers_data[0][1].item_key, papers_data[0][0], seen_at)
    paper_repo.mark_seen(source2.source_id, papers_data[0][1].item_key, papers_data[0][0], seen_at)

    # Paper 1 只在 source1
    paper_repo.mark_seen(source1.source_id, papers_data[1][1].item_key, papers_data[1][0], seen_at)

    # Paper 2 只在 source2
    paper_repo.mark_seen(source2.source_id, papers_data[2][1].item_key, papers_data[2][0], seen_at)

    # 查询两个 sources
    results = paper_repo.list_papers_by_sources_and_window(
        source_ids=[source1.source_id, source2.source_id],
        limit=10,
    )

    # 应该返回 3 个唯一的 papers（DISTINCT 去重）
    assert len(results) == 3

    # 验证按 published_at 倒序
    assert results[0].published_at > results[1].published_at > results[2].published_at


def test_list_papers_by_sources_and_window_datetime_filter(paper_repo: PaperRepository):
    """测试时间窗口过滤"""
    # 创建 source
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    # 创建 5 个 papers，日期分别为 2024-01-01, 01-10, 01-15, 01-20, 01-31
    dates = [
        datetime(2024, 1, 1),
        datetime(2024, 1, 10),
        datetime(2024, 1, 15),
        datetime(2024, 1, 20),
        datetime(2024, 1, 31),
    ]
    seen_at = datetime.utcnow()

    for i, date in enumerate(dates):
        record = PaperRecord(
            canonical_id=f"paper:240{i}.12345",
            canonical_url=f"https://example.com/240{i}.12345",
            title=f"Paper {i}",
            item_key=f"v1:240{i}.12345",
            published_at=date,
        )
        paper_id = paper_repo.upsert_paper(record)
        paper_repo.mark_seen(source.source_id, record.item_key, paper_id, seen_at)

    # 查询窗口 [2024-01-10, 2024-01-25)
    results = paper_repo.list_papers_by_sources_and_window(
        source_ids=[source.source_id],
        since=datetime(2024, 1, 10),
        until=datetime(2024, 1, 25),
        limit=10,
    )

    # 应该返回 3 个 papers（indices 1, 2, 3）
    assert len(results) == 3

    # 验证所有返回的 papers 都在窗口内
    for paper in results:
        assert paper.published_at is not None
        assert datetime(2024, 1, 10) <= paper.published_at < datetime(2024, 1, 25)


def test_list_papers_by_sources_and_window_edge_cases(paper_repo: PaperRepository):
    """测试边界情况"""
    # 创建 source
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    # 测试 1: 空 source_ids 列表
    results = paper_repo.list_papers_by_sources_and_window(
        source_ids=[],
        limit=10,
    )
    assert results == []

    # 测试 2: 不存在的 source_id
    results = paper_repo.list_papers_by_sources_and_window(
        source_ids=["nonexistent_source"],
        limit=10,
    )
    assert results == []

    # 测试 3: Paper 有 NULL published_at
    seen_at = datetime.utcnow()

    # Paper with NULL published_at
    record_null = PaperRecord(
        canonical_id="paper:null_date",
        canonical_url="https://example.com/null",
        title="Paper with NULL date",
        item_key="v1:null",
        published_at=None,
    )
    paper_id_null = paper_repo.upsert_paper(record_null)
    paper_repo.mark_seen(source.source_id, record_null.item_key, paper_id_null, seen_at)

    # Paper with valid published_at
    record_valid = PaperRecord(
        canonical_id="paper:valid_date",
        canonical_url="https://example.com/valid",
        title="Paper with valid date",
        item_key="v1:valid",
        published_at=datetime(2024, 1, 15),
    )
    paper_id_valid = paper_repo.upsert_paper(record_valid)
    paper_repo.mark_seen(source.source_id, record_valid.item_key, paper_id_valid, seen_at)

    # 无时间过滤：应该包含 NULL 日期的 paper
    results_no_filter = paper_repo.list_papers_by_sources_and_window(
        source_ids=[source.source_id],
        limit=10,
    )
    assert len(results_no_filter) == 2

    # 有时间过滤：NULL 日期的 paper 应该被排除
    results_with_filter = paper_repo.list_papers_by_sources_and_window(
        source_ids=[source.source_id],
        since=datetime(2024, 1, 1),
        limit=10,
    )
    assert len(results_with_filter) == 1
    assert results_with_filter[0].canonical_id == "paper:valid_date"


def test_paper_to_research_item(paper_repo: PaperRepository):
    """测试 paper 到 research item 的转换（完整数据）"""
    from core.paper.models import paper_to_research_item

    # 创建一个有完整元数据的 paper（包含长摘要）
    long_abstract = "A" * 250  # 250 字符的摘要
    record = PaperRecord(
        canonical_id="arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Test Paper with Full Metadata",
        item_key="v1:arxiv:2401.12345",
        abstract=long_abstract,
        published_at=datetime(2024, 1, 15, 10, 30, 0),
        authors=["Alice Smith", "Bob Jones"],
        venue="ICLR 2024",
        doi="10.1234/test.doi",
        pdf_url="https://arxiv.org/pdf/2401.12345.pdf",
        external_ids={"arxiv_id": "2401.12345", "doi": "10.1234/test.doi"},
    )
    paper_id = paper_repo.upsert_paper(record)
    paper = paper_repo.get_paper(paper_id)

    # 转换为 research item
    item = paper_to_research_item(paper)

    # 验证所有字段
    assert item["item_key"] == "arxiv:2401.12345"
    assert item["title"] == "Test Paper with Full Metadata"
    assert item["url"] == "https://arxiv.org/abs/2401.12345"
    assert item["published_at"] == "2024-01-15T10:30:00"
    assert item["authors"] == ["Alice Smith", "Bob Jones"]
    assert item["venue"] == "ICLR 2024"

    # 验证 summary 被截断到 200 字符
    assert item["summary"] is not None
    assert len(item["summary"]) <= 200
    assert item["summary"].endswith("...")

    # 验证 meta 结构
    assert item["meta"]["doi"] == "10.1234/test.doi"
    assert item["meta"]["pdf_url"] == "https://arxiv.org/pdf/2401.12345.pdf"
    assert item["meta"]["external_ids"] == {"arxiv_id": "2401.12345", "doi": "10.1234/test.doi"}


def test_paper_to_research_item_minimal(paper_repo: PaperRepository):
    """测试 paper 到 research item 的转换（最小数据）"""
    from core.paper.models import paper_to_research_item

    # 创建只有必需字段的 paper
    record = PaperRecord(
        canonical_id="arxiv:2401.99999",
        canonical_url=None,
        title="Minimal Paper",
        item_key="v1:arxiv:2401.99999",
        abstract=None,
        published_at=None,
        authors=None,
        venue=None,
        doi=None,
        pdf_url=None,
        external_ids=None,
    )
    paper_id = paper_repo.upsert_paper(record)
    paper = paper_repo.get_paper(paper_id)

    # 转换为 research item
    item = paper_to_research_item(paper)

    # 验证必需字段
    assert item["item_key"] == "arxiv:2401.99999"
    assert item["title"] == "Minimal Paper"

    # 验证可选字段为 None
    assert item["url"] is None
    assert item["published_at"] is None
    assert item["summary"] is None
    assert item["authors"] is None
    assert item["venue"] is None
    assert item["meta"]["doi"] is None
    assert item["meta"]["pdf_url"] is None
    assert item["meta"]["external_ids"] is None


# ========== Module 4: Paper Runs ==========


def test_create_and_finish_run(paper_repo: PaperRepository):
    """测试 run 创建和完成"""
    # 创建 source
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    # 创建 run
    run_id = paper_repo.create_run(source.source_id, job_id="job_123")
    assert run_id == "job_123"

    # 完成 run
    paper_repo.finish_run(
        run_id=run_id,
        status="succeeded",
        fetched_count=10,
        processed_count=10,
        cursor_after={"start": 10},
        metrics={"api_calls": 1},
    )

    # 查询 run 历史
    runs = paper_repo.list_runs(source.source_id)
    assert len(runs) == 1
    assert runs[0].run_id == run_id
    assert runs[0].status == "succeeded"
    assert runs[0].fetched_count == 10


def test_create_run_no_collision_same_second(paper_repo: PaperRepository, monkeypatch):
    """同一 source 同秒两次 run 也必须唯一（P0-5）"""
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
    )

    import core.paper.repository as repo_mod
    from datetime import datetime as _dt

    class FrozenDateTime:
        @staticmethod
        def utcnow():
            return _dt(2026, 1, 1, 0, 0, 0)

    # Freeze to ensure deterministic "same second" scenario
    monkeypatch.setattr(repo_mod, "datetime", FrozenDateTime)

    run_id1 = paper_repo.create_run(source.source_id, job_id="job_a")
    run_id2 = paper_repo.create_run(source.source_id, job_id="job_b")

    assert run_id1 == "job_a"
    assert run_id2 == "job_b"
    assert run_id1 != run_id2
