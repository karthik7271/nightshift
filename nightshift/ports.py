from __future__ import annotations

from typing import Protocol

from .domain import Job, PatchPlan


class JobStore(Protocol):
    def create_if_absent(self, job: Job) -> tuple[Job, bool]: ...
    def save(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Job | None: ...


class JobDispatcher(Protocol):
    def dispatch(self, job_id: str) -> None: ...


class PlanningAgent(Protocol):
    def plan(self, repository: str, issue_number: int, title: str, body: str) -> PatchPlan: ...

