"""BoardEngine API Router

Board CRUD + Snapshot 查询端点
"""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas_board import (
    BoardOut,
    BoardRunJobOut,
    BoardSnapshotItemOut,
    BoardSnapshotOut,
    CreateBoardIn,
    SnapshotJobOut,
    TriggerBoardRunIn,
    UpdateBoardIn,
)
from core.models import Job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boards", tags=["boards"])
snapshots_router = APIRouter(prefix="/snapshots", tags=["boards"])


def _board_to_out(b) -> BoardOut:
    return BoardOut(
        board_id=b.board_id,
        provider=b.provider,
        kind=b.kind,
        name=b.name,
        config=json.loads(b.config_json),
        enabled=b.enabled,
        last_run_at=b.last_run_at,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def mount_board_routes(container: AppContainer) -> list[APIRouter]:
    """Mount board engine routes"""

    # ========== Board CRUD ==========

    @router.get("", response_model=list[BoardOut])
    def list_boards(
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BoardOut]:
        boards = container.board_repo.list_boards(
            provider=provider,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        return [_board_to_out(b) for b in boards]

    @router.post("", response_model=BoardOut)
    def create_board(data: CreateBoardIn) -> BoardOut:
        board = container.board_repo.upsert_board(
            provider=data.provider,
            kind=data.kind,
            name=data.name,
            config_json=json.dumps(data.config),
            enabled=data.enabled,
        )
        return _board_to_out(board)

    @router.get("/{board_id}", response_model=BoardOut)
    def get_board(board_id: str) -> BoardOut:
        board = container.board_repo.get_board(board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        return _board_to_out(board)

    @router.patch("/{board_id}", response_model=BoardOut)
    def update_board(board_id: str, data: UpdateBoardIn) -> BoardOut:
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.config is not None:
            updates["config_json"] = json.dumps(data.config)
        if data.enabled is not None:
            updates["enabled"] = 1 if data.enabled else 0

        board = container.board_repo.update_board(board_id, **updates)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        return _board_to_out(board)

    @router.delete("/{board_id}")
    def delete_board(board_id: str) -> dict:
        success = container.board_repo.delete_board(board_id)
        if not success:
            raise HTTPException(status_code=404, detail="Board not found")
        return {"ok": True}

    @router.post("/{board_id}/snapshot", response_model=SnapshotJobOut)
    def trigger_board_snapshot(
        board_id: str,
        response: Response,
        window: dict | None = None,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> SnapshotJobOut:
        """Trigger board snapshot job"""
        from backend.app.utils import wait_for_job
        board = container.board_repo.get_board(board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")

        window = window or {}
        window_since = window.get("since", "")
        window_until = window.get("until", "")
        config_hash = hashlib.sha256(board.config_json.encode()).hexdigest()[:8]
        idempotency_key = f"v1:board_snapshot:{board_id}:{window_since}:{window_until}:{config_hash}"

        job_id, is_new = container.job_repo.create_job_idempotent(
            job_type="board_snapshot",
            idempotency_key=idempotency_key,
            input_json={"board_id": board_id, "window": window},
        )

        if not wait:
            return SnapshotJobOut(job_id=job_id, snapshot_id=None, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202

        snapshot_id = None
        if result_job.output_json:
            output = json.loads(result_job.output_json)
            snapshot_id = output.get("snapshot_id")

        return SnapshotJobOut(
            job_id=job_id,
            snapshot_id=snapshot_id,
            status=result_job.status,
            error_message=result_job.error_message,
        )

    @router.post("/{board_id}/run", response_model=BoardRunJobOut)
    def trigger_board_run(
        board_id: str,
        data: TriggerBoardRunIn,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> BoardRunJobOut:
        """Trigger board run to compute delta between snapshots"""
        from backend.app.utils import wait_for_job
        board = container.board_repo.get_board(board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")

        current_snapshot = container.board_repo.get_snapshot(data.snapshot_id)
        if not current_snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        if current_snapshot.board_id != board_id:
            raise HTTPException(status_code=400, detail="Snapshot does not belong to this board")

        if data.baseline_snapshot_id:
            baseline_snapshot = container.board_repo.get_snapshot(data.baseline_snapshot_id)
            if not baseline_snapshot:
                raise HTTPException(status_code=404, detail="Baseline snapshot not found")
            if baseline_snapshot.board_id != board_id:
                raise HTTPException(status_code=400, detail="Baseline snapshot does not belong to this board")

        baseline_id = data.baseline_snapshot_id or "none"
        idempotency_key = f"v1:board_run:{board_id}:{data.snapshot_id}:{baseline_id}"

        job_id, is_new = container.job_repo.create_job_idempotent(
            job_type="board_run",
            idempotency_key=idempotency_key,
            input_json={
                "board_id": board_id,
                "snapshot_id": data.snapshot_id,
                "baseline_snapshot_id": data.baseline_snapshot_id,
            },
        )

        if not wait:
            return BoardRunJobOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202

        bundle_id = None
        artifact_id = None
        new_count = None
        removed_count = None
        kept_count = None

        if result_job.output_json:
            output = json.loads(result_job.output_json)
            bundle_id = output.get("bundle_id")
            artifact_id = output.get("artifact_id")
            if artifact_id:
                artifact = container.artifact_repo.get(artifact_id)
                if artifact and artifact.metadata:
                    new_count = artifact.metadata.get("new_count")
                    removed_count = artifact.metadata.get("removed_count")
                    kept_count = artifact.metadata.get("kept_count")

        return BoardRunJobOut(
            job_id=job_id,
            bundle_id=bundle_id,
            artifact_id=artifact_id,
            status=result_job.status,
            error_message=result_job.error_message,
            new_count=new_count,
            removed_count=removed_count,
            kept_count=kept_count,
        )

    @router.get("/{board_id}/runs", response_model=list[BoardRunJobOut])
    def list_board_runs(
        board_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BoardRunJobOut]:
        """List board run history

        Returns recent board runs for this board, ordered by created_at DESC.
        """
        # Verify board exists
        board = container.board_repo.get_board(board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")

        # Query artifacts by kind and board_id
        artifacts = container.artifact_repo.list(
            kind="board_bundle",
            limit=limit,
            offset=offset,
        )

        # Filter by board_id and convert to output
        results = []
        for artifact in artifacts:
            if artifact.metadata and artifact.metadata.get("board_id") == board_id:
                results.append(BoardRunJobOut(
                    job_id=artifact.job_id or "",
                    bundle_id=artifact.content.get("bundle_id"),
                    artifact_id=artifact.artifact_id,
                    status="succeeded",  # Artifact exists means job succeeded
                    error_message=None,
                    new_count=artifact.metadata.get("new_count"),
                    removed_count=artifact.metadata.get("removed_count"),
                    kept_count=artifact.metadata.get("kept_count"),
                ))

        return results

    # ========== Snapshot 查询 ==========

    @router.get("/{board_id}/snapshots", response_model=list[BoardSnapshotOut])
    def list_snapshots(
        board_id: str, limit: int = 100, offset: int = 0
    ) -> list[BoardSnapshotOut]:
        snapshots = container.board_repo.list_snapshots(
            board_id, limit=limit, offset=offset
        )
        return [_snapshot_to_out(s) for s in snapshots]

    @router.get("/{board_id}/snapshots/latest", response_model=BoardSnapshotOut)
    def get_latest_snapshot(board_id: str) -> BoardSnapshotOut:
        snap = container.board_repo.get_latest_snapshot(board_id)
        if not snap:
            raise HTTPException(status_code=404, detail="No snapshots found")
        return _snapshot_to_out(snap)

    @snapshots_router.get("/{snapshot_id}", response_model=BoardSnapshotOut)
    def get_snapshot(snapshot_id: str) -> BoardSnapshotOut:
        snap = container.board_repo.get_snapshot(snapshot_id)
        if not snap:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return _snapshot_to_out(snap)

    @snapshots_router.get(
        "/{snapshot_id}/items", response_model=list[BoardSnapshotItemOut]
    )
    def list_snapshot_items(
        snapshot_id: str, limit: int = 1000, offset: int = 0
    ) -> list[BoardSnapshotItemOut]:
        items = container.board_repo.list_snapshot_items(
            snapshot_id, limit=limit, offset=offset
        )
        return [
            BoardSnapshotItemOut(
                snapshot_id=i.snapshot_id,
                item_key=i.item_key,
                source_order=i.source_order,
                title=i.title,
                url=i.url,
                meta=json.loads(i.meta_json) if i.meta_json else None,
            )
            for i in items
        ]

    return [router, snapshots_router]


def _snapshot_to_out(s) -> BoardSnapshotOut:
    return BoardSnapshotOut(
        snapshot_id=s.snapshot_id,
        board_id=s.board_id,
        window_since=s.window_since,
        window_until=s.window_until,
        captured_at=s.captured_at,
        raw_capture_ref=s.raw_capture_ref,
        adapter_version=s.adapter_version,
        created_at=s.created_at,
    )
