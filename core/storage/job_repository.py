from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta

from core.models import Job, PendingConfirm, ProvenanceEvent, RawCapture, Schedule, SnifferRunLog, ToolCall
from core.storage.db import Database


def generate_deterministic_job_id(
    job_type: str,
    idempotency_key: str,
) -> str:
    """Generate deterministic job_id from job_type and idempotency_key

    Args:
        job_type: Job type (e.g., "board_snapshot", "research_run")
        idempotency_key: Idempotency key following format:
            v1:{job_type}:{entity_id}:{window_since}:{window_until}:{params_hash}

    Returns:
        job_id: Deterministic job ID (job_{12-char-hex})

    Examples:
        >>> generate_deterministic_job_id(
        ...     "board_snapshot",
        ...     "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
        ... )
        'job_a1b2c3d4e5f6'
    """
    # Combine job_type and idempotency_key
    key_str = f"{job_type}:{idempotency_key}"
    hash_hex = hashlib.sha256(key_str.encode()).hexdigest()[:12]

    return f"job_{hash_hex}"


class JobRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- Job CRUD ---

    def create_job(self, job: Job) -> Job:
        """Create a new job (non-idempotent)

        Note: For idempotent job creation, use create_job_idempotent() instead.
        This method does not check for existing jobs and will fail if job_id
        already exists (PRIMARY KEY constraint violation).

        Args:
            job: Job object with job_id already set

        Returns:
            Created Job object
        """
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO jobs
                   (job_id, job_type, status, input_json, output_json,
                    error_class, error_message, created_at, started_at, finished_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.job_id, job.job_type, job.status, job.input_json,
                    job.output_json, job.error_class, job.error_message,
                    job.created_at.isoformat() if job.created_at else datetime.utcnow().isoformat(),
                    job.started_at.isoformat() if job.started_at else None,
                    job.finished_at.isoformat() if job.finished_at else None,
                    json.dumps(job.metadata),
                ),
            )
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job.job_id,)).fetchone()
        return _row_to_job(row)

    def create_job_idempotent(
        self,
        job_type: str,
        idempotency_key: str,
        input_json: dict,
        metadata: dict | None = None,
    ) -> tuple[str, bool]:
        """Create job idempotently using deterministic job_id

        If a job with the same job_type and idempotency_key already exists,
        returns the existing job_id without creating a new job.

        Args:
            job_type: Job type
            idempotency_key: Idempotency key (see format spec in docs/follow.md)
            input_json: Job input data (will be JSON-serialized)
            metadata: Optional metadata dict

        Returns:
            (job_id, is_new): Tuple of job_id and whether it was newly created

        Examples:
            >>> job_id, is_new = repo.create_job_idempotent(
            ...     job_type="board_snapshot",
            ...     idempotency_key="v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc",
            ...     input_json={"board_id": "board_123"},
            ... )
            >>> print(f"Job {job_id}, new={is_new}")
            Job job_a1b2c3d4e5f6, new=True
        """
        job_id = generate_deterministic_job_id(job_type, idempotency_key)

        with self.db.connect() as conn:
            # Check if job already exists
            existing = conn.execute(
                "SELECT job_id, status FROM jobs WHERE job_id = ?",
                (job_id,)
            ).fetchone()

            if existing:
                # Job already exists, return existing job_id
                return (job_id, False)

            # Job doesn't exist, create new one
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, job_type, status, input_json, metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job_type,
                    "queued",
                    json.dumps(input_json),
                    json.dumps(metadata) if metadata else "{}",
                    now,
                ),
            )

            return (job_id, True)

    def find_job_by_idempotency_key(
        self,
        job_type: str,
        idempotency_key: str,
    ) -> Job | None:
        """Find job by idempotency key

        Args:
            job_type: Job type
            idempotency_key: Idempotency key

        Returns:
            Job object if found, None otherwise
        """
        job_id = generate_deterministic_job_id(job_type, idempotency_key)
        return self.get_job(job_id)

    def update_status(
        self, job_id: str, status: str, *,
        error_class: str | None = None,
        error_message: str | None = None,
        output_json: str | None = None,
    ) -> Job | None:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            if status == "running":
                conn.execute(
                    "UPDATE jobs SET status=?, started_at=? WHERE job_id=?",
                    (status, now, job_id),
                )
            elif status in ("succeeded", "failed", "cancelled"):
                conn.execute(
                    """UPDATE jobs SET status=?, finished_at=?, error_class=?,
                       error_message=?, output_json=? WHERE job_id=?""",
                    (status, now, error_class, error_message, output_json, job_id),
                )
            else:
                conn.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, job_id))
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def update_metadata(self, job_id: str, metadata: dict) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE jobs SET metadata_json = ? WHERE job_id = ?",
                (json.dumps(metadata), job_id),
            )

    def merge_metadata(self, job_id: str, metadata: dict) -> Job | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT metadata_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            current = json.loads(row["metadata_json"] or "{}")
            current.update(metadata)
            conn.execute(
                "UPDATE jobs SET metadata_json = ? WHERE job_id = ?",
                (json.dumps(current), job_id),
            )
            updated = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(updated) if updated else None

    def cancel_job(self, job_id: str) -> Job | None:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=?, error_class=NULL, error_message=NULL, output_json=NULL WHERE job_id=? AND status='queued'",
                (now, job_id),
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def request_cancel(self, job_id: str) -> Job | None:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            row = conn.execute("SELECT status, metadata_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row or row["status"] != "running":
                return None
            metadata = json.loads(row["metadata_json"] or "{}")
            metadata["cancel_requested"] = True
            metadata["cancel_requested_at"] = now
            conn.execute(
                "UPDATE jobs SET metadata_json = ? WHERE job_id = ? AND status = 'running'",
                (json.dumps(metadata), job_id),
            )
            updated = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(updated) if updated else None

    def get_job(self, job_id: str) -> Job | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, job_type: str | None = None, status: str | None = None, limit: int = 50) -> list[Job]:
        query = "SELECT * FROM jobs"
        where: list[str] = []
        params: list[object] = []
        if job_type:
            where.append("job_type = ?")
            params.append(job_type)
        if status:
            where.append("status = ?")
            params.append(status)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_job(row) for row in rows]

    def fetch_and_lock_next_queued_job(
        self,
        job_types: list[str] | None = None,
    ) -> "Job | None":
        """Atomically fetch and lock the next queued job (queued → running).
        Concurrency-safe: uses a conditional UPDATE as an optimistic lock;
        rowcount=0 means another worker claimed it first.
        """
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            where = "status = 'queued'"
            params: list = []
            if job_types:
                placeholders = ",".join("?" * len(job_types))
                where += f" AND job_type IN ({placeholders})"
                params.extend(job_types)

            row = conn.execute(
                f"SELECT job_id FROM jobs WHERE {where} ORDER BY created_at ASC LIMIT 1",
                params,
            ).fetchone()
            if not row:
                return None

            job_id = row["job_id"]
            cursor = conn.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE job_id=? AND status='queued'",
                (now, job_id),
            )
            if cursor.rowcount == 0:
                return None  # claimed by another worker

            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return _row_to_job(row)

    def reset_stale_running_jobs(self, stale_minutes: int = 30) -> int:
        """Reset jobs stuck in 'running' (e.g. after worker crash) back to 'queued'."""
        threshold = (datetime.utcnow() - timedelta(minutes=stale_minutes)).isoformat()
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status='queued', started_at=NULL "
                "WHERE status='running' AND started_at < ?",
                (threshold,),
            )
        return cursor.rowcount

    # --- Provenance Events ---

    def append_event(self, event: ProvenanceEvent) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO provenance_events
                   (event_id, run_id, event_type, actor, entity_refs, payload_json, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id, event.run_id, event.event_type, event.actor,
                    json.dumps(event.entity_refs), json.dumps(event.payload),
                    event.ts.isoformat() if event.ts else datetime.utcnow().isoformat(),
                ),
            )

    def list_events(self, run_id: str) -> list[ProvenanceEvent]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM provenance_events WHERE run_id = ? ORDER BY ts ASC", (run_id,)
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    # --- Tool Calls ---

    def record_tool_call(self, tc: ToolCall) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO tool_calls
                   (tool_call_id, run_id, tool_name, tool_version, request_json,
                    status, output_ref, error_message, idempotency_key, started_at, finished_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tc.tool_call_id, tc.run_id, tc.tool_name, tc.tool_version,
                    tc.request_json, tc.status, tc.output_ref, tc.error_message,
                    tc.idempotency_key,
                    tc.started_at.isoformat() if tc.started_at else datetime.utcnow().isoformat(),
                    tc.finished_at.isoformat() if tc.finished_at else None,
                ),
            )

    def finish_tool_call(
        self, tool_call_id: str, status: str, *,
        output_ref: str | None = None, error: str | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE tool_calls SET status=?, output_ref=?, error_message=?, finished_at=? WHERE tool_call_id=?",
                (status, output_ref, error, now, tool_call_id),
            )

    # --- Sniffer Run Log ---

    def save_sniffer_run(self, run: SnifferRunLog) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO sniffer_run_log
                   (run_id, job_id, query_json, pack_id, status, result_count,
                    channels_used, error_message, started_at, finished_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.run_id, run.job_id, run.query_json, run.pack_id,
                    run.status, run.result_count, json.dumps(run.channels_used),
                    run.error_message,
                    run.started_at.isoformat() if run.started_at else datetime.utcnow().isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                    json.dumps(run.metadata),
                ),
            )

    def finish_sniffer_run(
        self, run_id: str, status: str, result_count: int, *,
        error: str | None = None,
        channels_succeeded: list[str] | None = None,
        channels_failed: list[str] | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        meta = {}
        if channels_succeeded is not None:
            meta["channels_succeeded"] = channels_succeeded
        if channels_failed is not None:
            meta["channels_failed"] = channels_failed
        with self.db.connect() as conn:
            if meta:
                conn.execute(
                    """UPDATE sniffer_run_log
                       SET status=?, result_count=?, error_message=?, finished_at=?, metadata_json=?
                       WHERE run_id=?""",
                    (status, result_count, error, now, json.dumps(meta), run_id),
                )
            else:
                conn.execute(
                    "UPDATE sniffer_run_log SET status=?, result_count=?, error_message=?, finished_at=? WHERE run_id=?",
                    (status, result_count, error, now, run_id),
                )

    def get_sniffer_run(self, run_id: str) -> SnifferRunLog | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM sniffer_run_log WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_sniffer_run(row) if row else None

    def list_sniffer_runs(self, limit: int = 50) -> list[SnifferRunLog]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sniffer_run_log ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_sniffer_run(row) for row in rows]

    # --- Schedules ---

    def upsert_schedule(self, s: Schedule) -> Schedule:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO schedules
                   (schedule_id, schedule_type, ref_id, interval_seconds, cron_expr,
                    next_run_at, last_run_at, enabled, locked_until, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(schedule_type, ref_id)
                   DO UPDATE SET
                       interval_seconds = excluded.interval_seconds,
                       cron_expr = excluded.cron_expr,
                       next_run_at = excluded.next_run_at,
                       enabled = excluded.enabled""",
                (
                    s.schedule_id, s.schedule_type, s.ref_id, s.interval_seconds,
                    s.cron_expr,
                    s.next_run_at.isoformat() if s.next_run_at else None,
                    s.last_run_at.isoformat() if s.last_run_at else None,
                    1 if s.enabled else 0,
                    s.locked_until.isoformat() if s.locked_until else None,
                    s.created_at.isoformat() if s.created_at else now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM schedules WHERE schedule_type = ? AND ref_id = ?",
                (s.schedule_type, s.ref_id),
            ).fetchone()
        return _row_to_schedule(row)

    def get_schedule(self, schedule_id: str) -> Schedule | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)).fetchone()
        return _row_to_schedule(row) if row else None

    def delete_schedule(self, schedule_id: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
        return cursor.rowcount > 0

    def list_due_schedules(self, now: datetime) -> list[Schedule]:
        now_iso = now.isoformat()
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM schedules
                   WHERE enabled = 1
                     AND next_run_at <= ?
                     AND (locked_until IS NULL OR locked_until <= ?)""",
                (now_iso, now_iso),
            ).fetchall()
        return [_row_to_schedule(row) for row in rows]

    def lock_schedule(self, schedule_id: str, until: datetime) -> bool:
        now_iso = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """UPDATE schedules SET locked_until = ?
                   WHERE schedule_id = ?
                     AND (locked_until IS NULL OR locked_until <= ?)""",
                (until.isoformat(), schedule_id, now_iso),
            )
        return cursor.rowcount > 0

    def finish_schedule_run(self, schedule_id: str, next_run_at: datetime) -> None:
        now_iso = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """UPDATE schedules
                   SET last_run_at = ?, next_run_at = ?, locked_until = NULL
                   WHERE schedule_id = ?""",
                (now_iso, next_run_at.isoformat(), schedule_id),
            )

    # --- Pending Confirms ---

    def create_confirm(self, pc: PendingConfirm) -> PendingConfirm:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO pending_confirms
                   (confirm_id, job_id, action_type, payload_json, status, created_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pc.confirm_id,
                    pc.job_id,
                    pc.action_type,
                    pc.payload_json,
                    pc.status,
                    now,
                    json.dumps(pc.metadata),
                ),
            )
            row = conn.execute(
                "SELECT * FROM pending_confirms WHERE confirm_id = ?", (pc.confirm_id,)
            ).fetchone()
        return _row_to_confirm(row)

    def get_confirm(self, confirm_id: str) -> PendingConfirm | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_confirms WHERE confirm_id = ?", (confirm_id,)
            ).fetchone()
        return _row_to_confirm(row) if row else None

    def list_confirms(self, status: str = "pending", limit: int = 50) -> list[PendingConfirm]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_confirms WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [_row_to_confirm(row) for row in rows]

    def resolve_confirm(self, confirm_id: str, status: str) -> PendingConfirm | None:
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE pending_confirms SET status = ?, resolved_at = ? WHERE confirm_id = ?",
                (status, now, confirm_id),
            )
            row = conn.execute(
                "SELECT * FROM pending_confirms WHERE confirm_id = ?", (confirm_id,)
            ).fetchone()
        return _row_to_confirm(row) if row else None

    def update_confirm_metadata(self, confirm_id: str, metadata: dict) -> PendingConfirm | None:
        current = self.get_confirm(confirm_id)
        if not current:
            return None
        merged = dict(current.metadata)
        merged.update(metadata)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE pending_confirms SET metadata_json = ? WHERE confirm_id = ?",
                (json.dumps(merged), confirm_id),
            )
            row = conn.execute(
                "SELECT * FROM pending_confirms WHERE confirm_id = ?", (confirm_id,)
            ).fetchone()
        return _row_to_confirm(row) if row else None

    # --- Raw Captures ---

    def save_raw_capture(
        self,
        capture_id: str,
        tool_call_id: str | None,
        channel: str,
        content_ref: str,
        checksum: str | None,
        content_type: str = "json",
    ) -> None:
        """Save a raw capture record"""
        now = datetime.utcnow().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO raw_captures
                   (capture_id, tool_call_id, channel, content_ref, checksum, content_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (capture_id, tool_call_id, channel, content_ref, checksum, content_type, now),
            )

    def get_raw_capture(self, capture_id: str) -> RawCapture | None:
        """Get a raw capture by capture_id"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM raw_captures WHERE capture_id = ?", (capture_id,)
            ).fetchone()
        return _row_to_raw_capture(row) if row else None

    def find_raw_capture_by_tool_call(self, tool_call_id: str) -> RawCapture | None:
        """Find a raw capture by tool_call_id"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM raw_captures WHERE tool_call_id = ?", (tool_call_id,)
            ).fetchone()
        return _row_to_raw_capture(row) if row else None


# --- Row mappers ---

def _row_to_job(row) -> Job:
    return Job(
        job_id=row["job_id"],
        job_type=row["job_type"],
        status=row["status"],
        input_json=row["input_json"] or "{}",
        output_json=row["output_json"],
        error_class=row["error_class"],
        error_message=row["error_message"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_event(row) -> ProvenanceEvent:
    return ProvenanceEvent(
        event_id=row["event_id"],
        run_id=row["run_id"],
        event_type=row["event_type"],
        actor=row["actor"] or "system",
        entity_refs=json.loads(row["entity_refs"] or "{}"),
        payload=json.loads(row["payload_json"] or "{}"),
        ts=datetime.fromisoformat(row["ts"]) if row["ts"] else None,
    )


def _row_to_sniffer_run(row) -> SnifferRunLog:
    return SnifferRunLog(
        run_id=row["run_id"],
        job_id=row["job_id"],
        query_json=row["query_json"] or "{}",
        pack_id=row["pack_id"],
        status=row["status"],
        result_count=row["result_count"] or 0,
        channels_used=json.loads(row["channels_used"] or "[]"),
        error_message=row["error_message"],
        started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_schedule(row) -> Schedule:
    return Schedule(
        schedule_id=row["schedule_id"],
        schedule_type=row["schedule_type"],
        ref_id=row["ref_id"],
        interval_seconds=row["interval_seconds"],
        cron_expr=row["cron_expr"],
        next_run_at=datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
        enabled=bool(row["enabled"]),
        locked_until=datetime.fromisoformat(row["locked_until"]) if row["locked_until"] else None,
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_confirm(row) -> PendingConfirm:
    return PendingConfirm(
        confirm_id=row["confirm_id"],
        job_id=row["job_id"],
        action_type=row["action_type"],
        payload_json=row["payload_json"] or "{}",
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_raw_capture(row) -> RawCapture:
    return RawCapture(
        capture_id=row["capture_id"],
        tool_call_id=row["tool_call_id"],
        channel=row["channel"],
        content_ref=row["content_ref"],
        checksum=row["checksum"],
        content_type=row["content_type"] or "json",
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )
