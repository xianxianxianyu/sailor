from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MainFlowTask:
    task_id: str
    task_type: str
    title: str
    description: str
    resource_id: str
    priority: str
    status: str
