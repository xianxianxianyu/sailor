"""Manual verification script for job idempotency

Run this script to manually verify the idempotency implementation works correctly.
"""
from pathlib import Path

from core.storage.db import Database
from core.storage.job_repository import JobRepository, generate_deterministic_job_id


def main():
    # Create temporary database
    db_path = Path("data/test_idempotency_manual.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = Database(db_path)
    db.init_schema()
    repo = JobRepository(db)

    print("=" * 60)
    print("Job Idempotency Manual Verification")
    print("=" * 60)

    # Test 1: Deterministic ID generation
    print("\n1. Testing deterministic ID generation...")
    job_id1 = generate_deterministic_job_id(
        "board_snapshot",
        "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    )
    job_id2 = generate_deterministic_job_id(
        "board_snapshot",
        "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    )
    assert job_id1 == job_id2
    print(f"   [OK] Deterministic ID: {job_id1}")
    print(f"   [OK] Same inputs produce same ID: {job_id1 == job_id2}")

    # Test 2: Idempotent creation
    print("\n2. Testing idempotent job creation...")
    job_id_a, is_new_a = repo.create_job_idempotent(
        job_type="board_snapshot",
        idempotency_key="v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc",
        input_json={"board_id": "board_123"},
    )
    print(f"   [OK] First call: job_id={job_id_a}, is_new={is_new_a}")

    job_id_b, is_new_b = repo.create_job_idempotent(
        job_type="board_snapshot",
        idempotency_key="v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc",
        input_json={"board_id": "board_123"},
    )
    print(f"   [OK] Second call: job_id={job_id_b}, is_new={is_new_b}")

    assert job_id_a == job_id_b
    assert is_new_a is True
    assert is_new_b is False
    print(f"   [OK] Idempotency verified: same job_id returned, is_new=False on second call")

    # Test 3: Find by idempotency key
    print("\n3. Testing find by idempotency key...")
    found_job = repo.find_job_by_idempotency_key(
        "board_snapshot",
        "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    )
    assert found_job is not None
    assert found_job.job_id == job_id_a
    print(f"   [OK] Found job: {found_job.job_id}")
    print(f"   [OK] Job type: {found_job.job_type}")
    print(f"   [OK] Status: {found_job.status}")

    # Test 4: Different keys produce different jobs
    print("\n4. Testing different idempotency keys...")
    job_id_c, is_new_c = repo.create_job_idempotent(
        job_type="research_run",
        idempotency_key="v1:research_run:prog_ai:2024-01-01:2024-01-07",
        input_json={"program_id": "prog_ai"},
    )
    print(f"   [OK] Different key: job_id={job_id_c}, is_new={is_new_c}")
    assert job_id_c != job_id_a
    assert is_new_c is True
    print(f"   [OK] Different idempotency keys produce different job_ids")

    print("\n" + "=" * 60)
    print("[OK] All manual verification tests passed!")
    print("=" * 60)

    # Cleanup
    db_path.unlink(missing_ok=True)
    print(f"\nCleaned up test database: {db_path}")


if __name__ == "__main__":
    main()
