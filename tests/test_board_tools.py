"""Tests for BoardEngine Tool Functions

Tests for adapters, raw_capture infrastructure, and tool functions.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.board import (
    BoardRepository,
    GitHubTrendingAdapter,
    HuggingFaceAdapter,
    boards_capture_github,
    boards_capture_huggingface,
    boards_snapshot_ingest,
)
from core.models import Job
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


# ========== Fixtures ==========


@pytest.fixture
def ctx_and_repos(tmp_path: Path):
    """Create RunContext + BoardRepository + JobRepository"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    board_repo = BoardRepository(db)

    # Create a job as run_id
    job = Job(job_id="test_job", job_type="board_snapshot")
    job_repo.create_job(job)

    ctx = RunContext(job_repo=job_repo, run_id="test_job", data_dir=tmp_path)

    return ctx, board_repo, job_repo


# ========== Adapter Tests ==========


def test_github_adapter_parse():
    """Test GitHubTrendingAdapter parsing"""
    adapter = GitHubTrendingAdapter()

    raw_data = {
        "repos": [
            {
                "owner": "microsoft",
                "name": "vscode",
                "description": "Visual Studio Code",
                "stars": 150000,
                "forks": 25000,
                "language": "TypeScript",
                "stars_today": 123,
            },
            {
                "owner": "facebook",
                "name": "react",
                "description": "A JavaScript library",
                "stars": 200000,
                "forks": 40000,
                "language": "JavaScript",
                "stars_today": 456,
            },
        ]
    }

    items = adapter.parse(raw_data)

    assert len(items) == 2
    assert items[0]["item_key"] == "v1:github_repo:microsoft/vscode"
    assert items[0]["source_order"] == 0
    assert items[0]["title"] == "microsoft/vscode"
    assert items[0]["url"] == "https://github.com/microsoft/vscode"
    assert items[0]["meta"]["stars"] == 150000
    assert items[0]["meta"]["language"] == "TypeScript"

    assert items[1]["item_key"] == "v1:github_repo:facebook/react"
    assert items[1]["source_order"] == 1


def test_github_adapter_empty():
    """Test GitHubTrendingAdapter with empty repos"""
    adapter = GitHubTrendingAdapter()
    raw_data = {"repos": []}

    items = adapter.parse(raw_data)

    assert len(items) == 0


def test_huggingface_adapter_models():
    """Test HuggingFaceAdapter for models"""
    adapter = HuggingFaceAdapter(kind="models")

    raw_data = {
        "items": [
            {
                "id": "openai/gpt-4",
                "author": "openai",
                "likes": 5000,
                "downloads": 100000,
                "tags": ["text-generation", "transformers"],
            },
            {
                "id": "meta-llama/Llama-2-7b",
                "author": "meta-llama",
                "likes": 3000,
                "downloads": 50000,
                "tags": ["text-generation"],
            },
        ]
    }

    items = adapter.parse(raw_data)

    assert len(items) == 2
    assert items[0]["item_key"] == "v1:hf_model:openai/gpt-4"
    assert items[0]["source_order"] == 0
    assert items[0]["title"] == "openai/gpt-4"
    assert items[0]["url"] == "https://huggingface.co/openai/gpt-4"
    assert items[0]["meta"]["likes"] == 5000
    assert items[0]["meta"]["author"] == "openai"


def test_huggingface_adapter_spaces():
    """Test HuggingFaceAdapter for spaces"""
    adapter = HuggingFaceAdapter(kind="spaces")

    raw_data = {
        "items": [
            {
                "id": "stabilityai/stable-diffusion",
                "author": "stabilityai",
                "likes": 2000,
                "downloads": 0,
                "tags": ["image-generation"],
            },
        ]
    }

    items = adapter.parse(raw_data)

    assert len(items) == 1
    assert items[0]["item_key"] == "v1:hf_space:stabilityai/stable-diffusion"
    assert items[0]["url"] == "https://huggingface.co/stabilityai/stable-diffusion"


# ========== RawCapture Infrastructure Tests ==========


def test_save_and_load_raw_capture(ctx_and_repos):
    """Test save_raw_capture and load_raw_capture"""
    ctx, board_repo, job_repo = ctx_and_repos

    content = json.dumps({"test": "data", "value": 123})
    capture_id = ctx.save_raw_capture(content, channel="test_channel")

    # Verify capture_id format
    assert capture_id.startswith("cap_")

    # Verify DB record
    rc = job_repo.get_raw_capture(capture_id)
    assert rc is not None
    assert rc.channel == "test_channel"
    assert rc.content_type == "json"
    assert rc.checksum is not None

    # Verify file exists
    file_path = Path(rc.content_ref)
    assert file_path.exists()

    # Load and verify content
    loaded_content = ctx.load_raw_capture(capture_id)
    assert loaded_content == content


def test_raw_capture_writes_file(ctx_and_repos):
    """Test that raw_capture actually writes file to disk"""
    ctx, board_repo, job_repo = ctx_and_repos

    content = "test content"
    capture_id = ctx.save_raw_capture(content, channel="test")

    # Get file path from DB
    rc = job_repo.get_raw_capture(capture_id)
    file_path = Path(rc.content_ref)

    # Verify file exists and has correct content
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == content


# ========== ToolFunction Tests (with HTTP mocking) ==========


@patch("core.board.tools.urlopen")
def test_boards_capture_github(mock_urlopen, ctx_and_repos):
    """Test boards_capture_github with mocked HTTP"""
    ctx, board_repo, job_repo = ctx_and_repos

    # Mock HTML response
    mock_html = """
    <html>
        <article class="Box-row">
            <h2><a href="/microsoft/vscode">microsoft/vscode</a></h2>
            <p class="col-9">Visual Studio Code</p>
            <svg class="octicon-star"></svg>
            <span itemprop="programmingLanguage">TypeScript</span>
        </article>
    </html>
    """
    mock_response = Mock()
    mock_response.read.return_value = mock_html.encode("utf-8")
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    mock_urlopen.return_value = mock_response

    # Call function
    capture_id = boards_capture_github(ctx, board_id="test_board", language="python", since="daily")

    # Verify capture_id returned
    assert capture_id.startswith("cap_")

    # Verify raw_capture saved
    rc = job_repo.get_raw_capture(capture_id)
    assert rc is not None
    assert rc.channel == "github"

    # Verify content
    content = ctx.load_raw_capture(capture_id)
    data = json.loads(content)
    assert "repos" in data
    assert "url" in data


@patch("core.board.tools.urlopen")
def test_boards_capture_huggingface(mock_urlopen, ctx_and_repos):
    """Test boards_capture_huggingface with mocked HTTP"""
    ctx, board_repo, job_repo = ctx_and_repos

    # Mock JSON response
    mock_data = [
        {"id": "openai/gpt-4", "author": "openai", "likes": 5000, "downloads": 100000, "tags": []},
    ]
    mock_response = Mock()
    mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    mock_urlopen.return_value = mock_response

    # Call function
    capture_id = boards_capture_huggingface(ctx, board_id="test_board", kind="models", limit=10)

    # Verify capture_id returned
    assert capture_id.startswith("cap_")

    # Verify raw_capture saved
    rc = job_repo.get_raw_capture(capture_id)
    assert rc is not None
    assert rc.channel == "huggingface"

    # Verify content
    content = ctx.load_raw_capture(capture_id)
    data = json.loads(content)
    assert "items" in data
    assert "kind" in data
    assert data["kind"] == "models"


def test_boards_snapshot_ingest(ctx_and_repos):
    """Test boards_snapshot_ingest"""
    ctx, board_repo, job_repo = ctx_and_repos

    # Create a board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="Python Trending",
        config_json=json.dumps({"language": "python"}),
    )

    # Create a raw capture
    raw_data = {
        "repos": [
            {
                "owner": "microsoft",
                "name": "vscode",
                "description": "VS Code",
                "stars": 150000,
                "forks": 25000,
                "language": "TypeScript",
                "stars_today": 123,
            },
        ],
        "captured_at": datetime.utcnow().isoformat(),
    }
    capture_id = ctx.save_raw_capture(json.dumps(raw_data), channel="github")

    # Ingest snapshot
    snapshot_id = boards_snapshot_ingest(
        ctx=ctx,
        board_repo=board_repo,
        board_id=board.board_id,
        raw_capture_ref=capture_id,
    )

    # Verify snapshot created
    snapshot = board_repo.get_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot.board_id == board.board_id
    assert snapshot.raw_capture_ref == capture_id

    # Verify snapshot items
    items = board_repo.list_snapshot_items(snapshot_id)
    assert len(items) == 1
    assert items[0].item_key == "v1:github_repo:microsoft/vscode"
    assert items[0].title == "microsoft/vscode"
    assert items[0].source_order == 0

    # Verify meta_json
    meta = json.loads(items[0].meta_json)
    assert meta["stars"] == 150000
    assert meta["language"] == "TypeScript"


def test_capture_and_ingest_e2e(ctx_and_repos):
    """End-to-end test: capture → ingest → verify snapshot items"""
    ctx, board_repo, job_repo = ctx_and_repos

    # Create board
    board = board_repo.upsert_board(
        provider="huggingface",
        kind="models",
        name="HF Models Trending",
        config_json="{}",
    )

    # Create raw capture manually (simulating capture function)
    raw_data = {
        "items": [
            {"id": "openai/gpt-4", "author": "openai", "likes": 5000, "downloads": 100000, "tags": []},
            {"id": "meta-llama/Llama-2-7b", "author": "meta-llama", "likes": 3000, "downloads": 50000, "tags": []},
        ],
        "kind": "models",
        "captured_at": datetime.utcnow().isoformat(),
    }
    capture_id = ctx.save_raw_capture(json.dumps(raw_data), channel="huggingface")

    # Ingest
    snapshot_id = boards_snapshot_ingest(
        ctx=ctx,
        board_repo=board_repo,
        board_id=board.board_id,
        raw_capture_ref=capture_id,
    )

    # Verify
    items = board_repo.list_snapshot_items(snapshot_id)
    assert len(items) == 2
    assert items[0].item_key == "v1:hf_model:openai/gpt-4"
    assert items[1].item_key == "v1:hf_model:meta-llama/Llama-2-7b"
