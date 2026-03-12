"""E2E automated test for Follow system

Runs full Follow system end-to-end tests verifying all component integration.

Usage:
    python tests/test_e2e_follow_auto.py

Or with pytest:
    pytest tests/test_e2e_follow_auto.py -v -s
"""
from __future__ import annotations

import time

import pytest
import requests

# Config
BASE_URL = "http://localhost:8000"
TIMEOUT = 60


def _cleanup_follows():
    """Delete all existing follows to start clean."""
    try:
        resp = requests.get(f"{BASE_URL}/follows")
        if resp.status_code == 200:
            for f in resp.json():
                requests.delete(f"{BASE_URL}/follows/{f['follow_id']}")
    except Exception:
        pass


def _cleanup_research_programs():
    """Delete all test research programs."""
    try:
        resp = requests.get(f"{BASE_URL}/research-programs")
        if resp.status_code == 200:
            for p in resp.json():
                if "e2e" in p.get("name", "").lower() or "test" in p.get("name", "").lower():
                    requests.delete(f"{BASE_URL}/research-programs/{p['program_id']}")
    except Exception:
        pass


def _cleanup_boards():
    """Delete all test boards."""
    try:
        resp = requests.get(f"{BASE_URL}/boards")
        if resp.status_code == 200:
            for b in resp.json():
                if "e2e" in b.get("name", "").lower() or "test" in b.get("name", "").lower():
                    requests.delete(f"{BASE_URL}/boards/{b['board_id']}")
    except Exception:
        pass


def _ensure_paper_source():
    """Ensure an arXiv paper source exists and has data.

    Returns source_id or None if unavailable.
    """
    # Check existing sources
    resp = requests.get(f"{BASE_URL}/paper-sources")
    if resp.status_code != 200:
        return None

    sources = resp.json()
    for s in sources:
        if s["platform"] == "arxiv":
            return s["source_id"]

    # Create one
    data = {
        "platform": "arxiv",
        "endpoint": "cat:cs.AI",
        "name": "arXiv AI - E2E Test",
        "config": {"max_results": 20},
        "enabled": True,
    }
    resp = requests.post(f"{BASE_URL}/paper-sources", json=data)
    if resp.status_code != 200:
        return None

    source_id = resp.json()["source_id"]

    # Trigger sync to fetch papers
    print(f"   Syncing paper source {source_id}...")
    resp = requests.post(f"{BASE_URL}/paper-sources/{source_id}/run")
    if resp.status_code == 200:
        status = resp.json().get("status", "unknown")
        print(f"   Sync status: {status}")
    else:
        print(f"   Sync failed: {resp.status_code} {resp.text[:200]}")

    return source_id


class TestE2EFollow:
    """E2E test class"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Check service and clean up before each test"""
        self._check_service()
        _cleanup_follows()

    def _check_service(self):
        try:
            response = requests.get(f"{BASE_URL}/healthz", timeout=5)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        except Exception as e:
            pytest.skip(f"Backend service not running: {e}")

    def wait_for_issue(self, follow_id: str, timeout: int = TIMEOUT) -> dict | None:
        """Wait for follow run to produce an issue."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(f"{BASE_URL}/follows/{follow_id}/issues/latest")
            if response.status_code == 200:
                issue = response.json()
                if issue is not None:
                    print(f"[OK] Issue generated for follow {follow_id}")
                    return issue
            time.sleep(2)
        raise TimeoutError(f"Follow {follow_id} did not produce an issue within {timeout}s")

    # ========== Scenario 1: Board-Only Follow ==========

    def test_scenario_1_board_only_follow(self):
        """Scenario 1: Board-Only Follow"""
        print("\n=== Scenario 1: Board-Only Follow ===")

        # 1. Create Board
        print("1. Creating GitHub Trending Board...")
        board_data = {
            "provider": "github",
            "kind": "trending",
            "name": "python-e2e-test",
            "config": {"language": "python"},
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/boards", json=board_data)
        assert response.status_code == 200, f"Failed to create board: {response.text}"
        board_id = response.json()["board_id"]
        print(f"[OK] Board created: {board_id}")

        # 2. Create Follow
        print("2. Creating Follow...")
        follow_data = {
            "name": "E2E Test - Board Only",
            "board_ids": [board_id],
            "research_program_ids": [],
            "window_policy": "daily",
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/follows", json=follow_data)
        assert response.status_code == 200, f"Failed to create follow: {response.text}"
        follow_id = response.json()["follow_id"]
        print(f"[OK] Follow created: {follow_id}")

        # 3. Trigger Follow run
        print("3. Triggering Follow run...")
        response = requests.post(f"{BASE_URL}/follows/{follow_id}/run")
        assert response.status_code == 200, f"Failed to trigger run: {response.text}"
        run_result = response.json()
        print(f"[OK] Follow run: {run_result['job_id']} (status={run_result['status']})")

        # 4. Wait for Issue
        print("4. Waiting for Issue...")
        issue = self.wait_for_issue(follow_id, timeout=120)

        # 5. Validate
        print("5. Validating Issue structure...")
        assert issue is not None
        assert "sections" in issue
        assert len(issue["sections"]) > 0
        board_section = issue["sections"][0]
        assert board_section["section_id"].startswith("board.")
        assert "items" in board_section
        print(f"[OK] Issue has {len(board_section['items'])} board items")

        # 6. Cleanup
        requests.delete(f"{BASE_URL}/follows/{follow_id}")
        requests.delete(f"{BASE_URL}/boards/{board_id}")
        print("[OK] Scenario 1 complete")

    # ========== Scenario 2: Research-Only Follow ==========

    def test_scenario_2_research_only_follow(self):
        """Scenario 2: Research-Only Follow"""
        print("\n=== Scenario 2: Research-Only Follow ===")

        # 1. Ensure paper source exists with data
        print("1. Ensuring paper source...")
        source_id = _ensure_paper_source()
        if not source_id:
            pytest.skip("No paper source available")
        print(f"[OK] Using source: {source_id}")

        # 2. Create Research Program
        print("2. Creating Research Program...")
        program_data = {
            "name": "E2E Test - AI Research",
            "description": "Automated test for research-only follow",
            "source_ids": [source_id],
            "filters": {"keywords": ["learning"]},
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/research-programs", json=program_data)
        assert response.status_code == 200, f"Failed to create program: {response.text}"
        program_id = response.json()["program_id"]
        print(f"[OK] Program created: {program_id}")

        # 3. Create Follow
        print("3. Creating Follow...")
        follow_data = {
            "name": "E2E Test - Research Only",
            "board_ids": [],
            "research_program_ids": [program_id],
            "window_policy": "weekly",
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/follows", json=follow_data)
        assert response.status_code == 200, f"Failed to create follow: {response.text}"
        follow_id = response.json()["follow_id"]
        print(f"[OK] Follow created: {follow_id}")

        # 4. Trigger Follow run
        print("4. Triggering Follow run...")
        response = requests.post(f"{BASE_URL}/follows/{follow_id}/run")
        assert response.status_code == 200, f"Failed to trigger run: {response.text}"
        run_result = response.json()
        print(f"[OK] Follow run: {run_result['job_id']} (status={run_result['status']})")

        # 5. Wait for Issue
        print("5. Waiting for Issue...")
        issue = self.wait_for_issue(follow_id, timeout=120)

        # 6. Validate
        print("6. Validating Issue structure...")
        assert issue is not None
        assert "sections" in issue
        assert len(issue["sections"]) > 0
        research_section = issue["sections"][0]
        assert research_section["section_id"].startswith("research.")
        assert "items" in research_section
        print(f"[OK] Issue has {len(research_section['items'])} research items")

        # 7. Cleanup
        requests.delete(f"{BASE_URL}/follows/{follow_id}")
        requests.delete(f"{BASE_URL}/research-programs/{program_id}")
        print("[OK] Scenario 2 complete")

    # ========== Scenario 3: Mixed Follow ==========

    def test_scenario_3_mixed_follow(self):
        """Scenario 3: Mixed Follow (Board + Research)"""
        print("\n=== Scenario 3: Mixed Follow ===")

        # 1. Create Board
        print("1. Creating Board...")
        board_data = {
            "provider": "github",
            "kind": "trending",
            "name": "mixed-e2e-test",
            "config": {"language": "python"},
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/boards", json=board_data)
        assert response.status_code == 200
        board_id = response.json()["board_id"]
        print(f"[OK] Board created: {board_id}")

        # 2. Ensure paper source
        print("2. Ensuring paper source...")
        source_id = _ensure_paper_source()
        if not source_id:
            requests.delete(f"{BASE_URL}/boards/{board_id}")
            pytest.skip("No paper source available")
        print(f"[OK] Using source: {source_id}")

        # 3. Create Research Program
        print("3. Creating Research Program...")
        program_data = {
            "name": "E2E Test - Mixed Research",
            "source_ids": [source_id],
            "filters": {"keywords": ["learning"]},
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/research-programs", json=program_data)
        assert response.status_code == 200
        program_id = response.json()["program_id"]
        print(f"[OK] Program created: {program_id}")

        # 4. Create Mixed Follow
        print("4. Creating Mixed Follow...")
        follow_data = {
            "name": "E2E Test - Mixed",
            "board_ids": [board_id],
            "research_program_ids": [program_id],
            "window_policy": "weekly",
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/follows", json=follow_data)
        assert response.status_code == 200
        follow_id = response.json()["follow_id"]
        print(f"[OK] Follow created: {follow_id}")

        # 5. Trigger run
        print("5. Triggering Follow run...")
        response = requests.post(f"{BASE_URL}/follows/{follow_id}/run")
        assert response.status_code == 200
        run_result = response.json()
        print(f"[OK] Follow run: {run_result['job_id']} (status={run_result['status']})")

        # 6. Wait for Issue
        print("6. Waiting for Issue...")
        issue = self.wait_for_issue(follow_id, timeout=120)

        # 7. Validate: should have both board and research sections
        print("7. Validating Issue structure...")
        assert len(issue["sections"]) >= 2, f"Expected >= 2 sections, got {len(issue['sections'])}"

        section_ids = [s["section_id"] for s in issue["sections"]]
        has_board = any(sid.startswith("board.") for sid in section_ids)
        has_research = any(sid.startswith("research.") for sid in section_ids)
        assert has_board, "Issue should contain board section"
        assert has_research, "Issue should contain research section"

        # Board should come before research
        board_idx = next(i for i, sid in enumerate(section_ids) if sid.startswith("board."))
        research_idx = next(i for i, sid in enumerate(section_ids) if sid.startswith("research."))
        assert board_idx < research_idx, "Board section should come before research"
        print(f"[OK] Issue has {len(issue['sections'])} sections in correct order")

        # 8. Cleanup
        requests.delete(f"{BASE_URL}/follows/{follow_id}")
        requests.delete(f"{BASE_URL}/boards/{board_id}")
        requests.delete(f"{BASE_URL}/research-programs/{program_id}")
        print("[OK] Scenario 3 complete")

    # ========== Scenario 4: Idempotency ==========

    def test_scenario_4_idempotency(self):
        """Scenario 4: Idempotency test"""
        print("\n=== Scenario 4: Idempotency ===")

        # 1. Create Board and Follow
        print("1. Creating test data...")
        board_data = {
            "provider": "github",
            "kind": "trending",
            "name": "idempotency-test",
            "config": {"language": "python"},
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/boards", json=board_data)
        board_id = response.json()["board_id"]

        follow_data = {
            "name": "E2E Test - Idempotency",
            "board_ids": [board_id],
            "window_policy": "daily",
            "enabled": True,
        }
        response = requests.post(f"{BASE_URL}/follows", json=follow_data)
        follow_id = response.json()["follow_id"]
        print("[OK] Test data created")

        # 2. Trigger twice with same explicit window
        print("2. Triggering twice with same window...")
        window = {
            "since": "2026-03-01T00:00:00",
            "until": "2026-03-02T00:00:00",
        }

        r1 = requests.post(f"{BASE_URL}/follows/{follow_id}/run", json={"window": window})
        assert r1.status_code == 200
        job_id_1 = r1.json()["job_id"]

        r2 = requests.post(f"{BASE_URL}/follows/{follow_id}/run", json={"window": window})
        assert r2.status_code == 200
        job_id_2 = r2.json()["job_id"]

        # 3. Verify same job_id
        print("3. Verifying idempotency...")
        assert job_id_1 == job_id_2, f"Job IDs differ: {job_id_1} != {job_id_2}"
        print("[OK] Idempotency verified")

        # 4. Cleanup
        requests.delete(f"{BASE_URL}/follows/{follow_id}")
        requests.delete(f"{BASE_URL}/boards/{board_id}")
        print("[OK] Scenario 4 complete")


if __name__ == "__main__":
    print("=" * 60)
    print("Follow System E2E Automated Test")
    print("=" * 60)

    # Check service
    try:
        response = requests.get(f"{BASE_URL}/healthz", timeout=5)
        if response.status_code != 200:
            print("[ERROR] Backend service not healthy")
            exit(1)
        print(f"[OK] Backend service running at {BASE_URL}")
    except Exception as e:
        print(f"[ERROR] Cannot connect: {e}")
        exit(1)

    # Cleanup
    print("\nCleaning up stale data...")
    _cleanup_follows()
    _cleanup_research_programs()
    _cleanup_boards()
    print("[OK] Cleanup done")

    # Run all scenarios
    test = TestE2EFollow()
    passed = 0
    failed = 0
    scenarios = [
        ("Scenario 1: Board-Only", test.test_scenario_1_board_only_follow),
        ("Scenario 2: Research-Only", test.test_scenario_2_research_only_follow),
        ("Scenario 3: Mixed Follow", test.test_scenario_3_mixed_follow),
        ("Scenario 4: Idempotency", test.test_scenario_4_idempotency),
    ]

    for name, fn in scenarios:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(scenarios)}")
    print("=" * 60)
    exit(1 if failed else 0)