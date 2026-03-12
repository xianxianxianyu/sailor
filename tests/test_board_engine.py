"""BoardEngine Unit Tests

测试 BoardRepository 的 CRUD 操作和幂等性
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core.board import BoardRepository
from core.storage import Database


@pytest.fixture
def board_repo(tmp_path: Path) -> BoardRepository:
    """创建临时 BoardRepository"""
    db_path = tmp_path / "test_board.db"
    db = Database(db_path)
    db.init_schema()
    return BoardRepository(db)


# ========== Board CRUD ==========


def test_create_board(board_repo: BoardRepository):
    """测试创建 board"""
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending-python",
        config_json=json.dumps({"language": "python"}),
    )

    assert board.board_id.startswith("board_github_")
    assert board.provider == "github"
    assert board.kind == "repos"
    assert board.name == "trending-python"
    assert board.enabled is True
    assert board.created_at is not None


def test_board_id_deterministic(board_repo: BoardRepository):
    """测试相同 provider+kind+name 生成相同 ID"""
    board1 = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending",
        config_json="{}",
    )

    board2 = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending",
        config_json=json.dumps({"updated": True}),
    )

    assert board1.board_id == board2.board_id


def test_upsert_board_update(board_repo: BoardRepository):
    """测试 upsert 更新已有 board"""
    board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending",
        config_json=json.dumps({"v": 1}),
    )

    updated = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending",
        config_json=json.dumps({"v": 2}),
        enabled=False,
    )

    assert json.loads(updated.config_json) == {"v": 2}
    assert updated.enabled is False


def test_list_boards_filter(board_repo: BoardRepository):
    """测试按 provider 和 enabled 过滤"""
    board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="trending",
        config_json="{}",
        enabled=True,
    )
    board_repo.upsert_board(
        provider="huggingface",
        kind="models",
        name="top-models",
        config_json="{}",
        enabled=False,
    )

    all_boards = board_repo.list_boards()
    assert len(all_boards) == 2

    enabled_boards = board_repo.list_boards(enabled_only=True)
    assert len(enabled_boards) == 1
    assert enabled_boards[0].provider == "github"

    gh_boards = board_repo.list_boards(provider="github")
    assert len(gh_boards) == 1


def test_update_board(board_repo: BoardRepository):
    """测试更新 name/config/enabled"""
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="original",
        config_json="{}",
    )

    updated = board_repo.update_board(
        board.board_id,
        name="renamed",
        config_json=json.dumps({"new": True}),
        enabled=0,
    )

    assert updated is not None
    assert updated.name == "renamed"
    assert json.loads(updated.config_json) == {"new": True}
    assert updated.enabled is False


def test_delete_board(board_repo: BoardRepository):
    """测试删除 board"""
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="to-delete",
        config_json="{}",
    )

    assert board_repo.delete_board(board.board_id) is True
    assert board_repo.get_board(board.board_id) is None


# ========== Snapshot ==========


def test_create_snapshot(board_repo: BoardRepository):
    """测试创建快照"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )
    captured = datetime(2024, 6, 1, 12, 0, 0)

    snap_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since="2024-05-01",
        window_until="2024-06-01",
        captured_at=captured,
    )

    assert snap_id.startswith("snap_")
    snap = board_repo.get_snapshot(snap_id)
    assert snap is not None
    assert snap.board_id == board.board_id
    assert snap.captured_at == captured


def test_snapshot_id_deterministic(board_repo: BoardRepository):
    """测试相同 board_id+captured_at 生成相同 ID"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )
    captured = datetime(2024, 6, 1, 12, 0, 0)

    snap_id1 = board_repo._generate_snapshot_id(board.board_id, captured)
    snap_id2 = board_repo._generate_snapshot_id(board.board_id, captured)
    assert snap_id1 == snap_id2


def test_list_snapshots(board_repo: BoardRepository):
    """测试列出快照（按 captured_at DESC）"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )

    board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 1, 1)
    )
    board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 6, 1)
    )

    snaps = board_repo.list_snapshots(board.board_id)
    assert len(snaps) == 2
    assert snaps[0].captured_at > snaps[1].captured_at


def test_get_latest_snapshot(board_repo: BoardRepository):
    """测试获取最新快照"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )

    board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 1, 1)
    )
    board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 6, 1)
    )

    latest = board_repo.get_latest_snapshot(board.board_id)
    assert latest is not None
    assert latest.captured_at == datetime(2024, 6, 1)


# ========== Snapshot Items ==========


def test_add_snapshot_items(board_repo: BoardRepository):
    """测试批量添加条目"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )
    snap_id = board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 6, 1)
    )

    board_repo.add_snapshot_items(snap_id, [
        {
            "item_key": "v1:github_repo:owner/repo1",
            "source_order": 0,
            "title": "Repo 1",
            "url": "https://github.com/owner/repo1",
            "meta_json": json.dumps({"stars": 100}),
        },
        {
            "item_key": "v1:github_repo:owner/repo2",
            "source_order": 1,
            "title": "Repo 2",
            "url": "https://github.com/owner/repo2",
        },
    ])

    items = board_repo.list_snapshot_items(snap_id)
    assert len(items) == 2


def test_list_snapshot_items(board_repo: BoardRepository):
    """测试列出条目（按 source_order）"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )
    snap_id = board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 6, 1)
    )

    board_repo.add_snapshot_items(snap_id, [
        {
            "item_key": "v1:b",
            "source_order": 1,
            "title": "Second",
            "url": "https://example.com/b",
        },
        {
            "item_key": "v1:a",
            "source_order": 0,
            "title": "First",
            "url": "https://example.com/a",
        },
    ])

    items = board_repo.list_snapshot_items(snap_id)
    assert items[0].source_order == 0
    assert items[0].title == "First"
    assert items[1].source_order == 1


# ========== 边界情况 ==========


def test_empty_board_list(board_repo: BoardRepository):
    """测试空列表"""
    assert board_repo.list_boards() == []


def test_nonexistent_board(board_repo: BoardRepository):
    """测试不存在的 board 返回 None"""
    assert board_repo.get_board("board_nonexistent_000000") is None


def test_snapshot_without_items(board_repo: BoardRepository):
    """测试无条目的快照"""
    board = board_repo.upsert_board(
        provider="github", kind="repos", name="test", config_json="{}"
    )
    snap_id = board_repo.create_snapshot(
        board.board_id, None, None, datetime(2024, 6, 1)
    )

    items = board_repo.list_snapshot_items(snap_id)
    assert items == []
