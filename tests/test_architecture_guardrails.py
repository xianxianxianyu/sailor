"""Architecture guardrails.

These tests enforce the repository's architectural baseline:
- Routers orchestrate only; they must not execute jobs directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def test_routers_do_not_execute_jobs_directly():
    repo_root = Path(__file__).resolve().parents[1]
    routers_dir = repo_root / "backend" / "app" / "routers"
    assert routers_dir.is_dir()

    forbidden_patterns = [
        re.compile(r"\bjob_runner\.run\s*\("),
        re.compile(r"\bcontainer\.job_runner\.run\s*\("),
        re.compile(r"\bcontainer\.\w+_agent\.\w+\s*\("),
    ]
    offenders: list[str] = []

    for path in routers_dir.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(p.search(text) for p in forbidden_patterns):
            offenders.append(str(path.relative_to(repo_root)))

    assert offenders == [], f"Routers must not execute jobs or call agents directly: {offenders}"


def test_dev_startup_includes_worker():
    repo_root = Path(__file__).resolve().parents[1]

    pkg_path = repo_root / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    dev_script = str((pkg.get("scripts") or {}).get("dev") or "")
    assert "dev:worker" in dev_script or "WORKER" in dev_script, "package.json scripts.dev must include worker"

    electron_main = repo_root / "electron" / "main.cjs"
    text = electron_main.read_text(encoding="utf-8", errors="replace")
    assert 'spawnScript("dev:worker")' in text, "electron dev must spawn dev:worker"
