from __future__ import annotations

from core.storage.repositories import ResourceRepository
from core.tasks.models import MainFlowTask


class MainUserFlowTaskPlanner:
    """Builds automation tasks from the markdown-defined main user flow."""

    def __init__(self, resource_repo: ResourceRepository) -> None:
        self.resource_repo = resource_repo

    def build_tasks(self) -> list[MainFlowTask]:
        inbox = self.resource_repo.list_resources(status="inbox")
        tasks: list[MainFlowTask] = []

        for resource in inbox:
            tasks.append(
                MainFlowTask(
                    task_id=f"scan_{resource.resource_id}",
                    task_type="scan",
                    title=f"Scan: {resource.title}",
                    description="Quickly scan topic + abstract in feed list.",
                    resource_id=resource.resource_id,
                    priority="medium",
                    status="todo",
                )
            )
            tasks.append(
                MainFlowTask(
                    task_id=f"review_{resource.resource_id}",
                    task_type="review",
                    title=f"Review: {resource.title}",
                    description="Read details and decide whether to archive into KB.",
                    resource_id=resource.resource_id,
                    priority="high",
                    status="todo",
                )
            )

        return tasks
