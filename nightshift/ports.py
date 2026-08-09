from __future__ import annotations

from typing import Protocol

from .domain import IssueRef, Job, PatchPlan


class JobStore(Protocol):
    def create_if_absent(self, job: Job) -> tuple[Job, bool]: ...
    def save(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def find_by_commit_sha(self, repository: str, commit_sha: str) -> list[Job]: ...


class JobDispatcher(Protocol):
    def dispatch(self, job_id: str) -> None: ...


class PlanningAgent(Protocol):
    def plan(self, issue: IssueRef) -> PatchPlan: ...
