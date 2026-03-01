"""Shared pytest fixtures — in-memory DB + container-like wiring."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the sailor package is importable
SAILOR_ROOT = Path(__file__).resolve().parent.parent
if str(SAILOR_ROOT) not in sys.path:
    sys.path.insert(0, str(SAILOR_ROOT))

from core.storage.db import Database
from core.storage.repositories import ResourceRepository, KnowledgeBaseRepository
from core.storage.tag_repository import TagRepository
from core.storage.analysis_repository import AnalysisRepository
from core.storage.source_repository import SourceRepository
from core.storage.job_repository import JobRepository


@pytest.fixture()
def db(tmp_path):
    """In-memory-like DB using a temp file (WAL needs a real file)."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


@pytest.fixture()
def resource_repo(db):
    return ResourceRepository(db)


@pytest.fixture()
def kb_repo(db):
    repo = KnowledgeBaseRepository(db)
    repo.ensure_defaults()
    return repo


@pytest.fixture()
def tag_repo(db):
    return TagRepository(db)


@pytest.fixture()
def analysis_repo(db):
    return AnalysisRepository(db)


@pytest.fixture()
def source_repo(db):
    return SourceRepository(db)


@pytest.fixture()
def job_repo(db):
    return JobRepository(db)
