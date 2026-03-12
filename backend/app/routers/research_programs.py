"""Research Program API Router

CRUD endpoints for research programs.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas_paper import (
    CreateResearchProgramIn,
    ResearchProgramOut,
    UpdateResearchProgramIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research-programs", tags=["research"])


def mount_research_program_routes(container: AppContainer) -> APIRouter:
    """Mount research program routes"""

    @router.get("", response_model=list[ResearchProgramOut])
    def list_research_programs(
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ResearchProgramOut]:
        """List all research programs"""
        programs = container.paper_repo.list_research_programs(
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        return [
            ResearchProgramOut(
                program_id=p.program_id,
                name=p.name,
                description=p.description,
                source_ids=json.loads(p.source_ids),
                filters=json.loads(p.filters_json) if p.filters_json else {},
                enabled=p.enabled,
                last_run_at=p.last_run_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in programs
        ]

    @router.post("", response_model=ResearchProgramOut)
    def create_research_program(data: CreateResearchProgramIn) -> ResearchProgramOut:
        """Create a new research program"""
        program = container.paper_repo.upsert_research_program(
            name=data.name,
            description=data.description,
            source_ids=data.source_ids,
            filters=data.filters,
            enabled=data.enabled,
        )
        return ResearchProgramOut(
            program_id=program.program_id,
            name=program.name,
            description=program.description,
            source_ids=json.loads(program.source_ids),
            filters=json.loads(program.filters_json) if program.filters_json else {},
            enabled=program.enabled,
            last_run_at=program.last_run_at,
            created_at=program.created_at,
            updated_at=program.updated_at,
        )

    @router.get("/{program_id}", response_model=ResearchProgramOut)
    def get_research_program(program_id: str) -> ResearchProgramOut:
        """Get research program details"""
        program = container.paper_repo.get_research_program(program_id)
        if not program:
            raise HTTPException(status_code=404, detail="Research program not found")

        return ResearchProgramOut(
            program_id=program.program_id,
            name=program.name,
            description=program.description,
            source_ids=json.loads(program.source_ids),
            filters=json.loads(program.filters_json) if program.filters_json else {},
            enabled=program.enabled,
            last_run_at=program.last_run_at,
            created_at=program.created_at,
            updated_at=program.updated_at,
        )

    @router.patch("/{program_id}", response_model=ResearchProgramOut)
    def update_research_program(
        program_id: str, data: UpdateResearchProgramIn
    ) -> ResearchProgramOut:
        """Update research program"""
        updated = container.paper_repo.update_research_program(
            program_id,
            name=data.name,
            description=data.description,
            source_ids=data.source_ids,
            filters=data.filters,
            enabled=data.enabled,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Research program not found")

        return ResearchProgramOut(
            program_id=updated.program_id,
            name=updated.name,
            description=updated.description,
            source_ids=json.loads(updated.source_ids),
            filters=json.loads(updated.filters_json) if updated.filters_json else {},
            enabled=updated.enabled,
            last_run_at=updated.last_run_at,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    @router.delete("/{program_id}")
    def delete_research_program(program_id: str) -> dict:
        """Delete research program"""
        deleted = container.paper_repo.delete_research_program(program_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Research program not found")
        return {"status": "deleted", "program_id": program_id}

    return router
