from __future__ import annotations

from .domain import Job


class InMemoryJobStore:
    """Local adapter. A Firestore adapter will satisfy the same interface in production."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}

    def create_if_absent(self, job: Job) -> tuple[Job, bool]:
        existing = self.jobs.get(job.id)
        if existing is not None:
            return existing, False
        self.jobs[job.id] = job
        return job, True

    def save(self, job: Job) -> None:
        self.jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def find_by_commit_sha(self, repository: str, commit_sha: str) -> list[Job]:
        return [job for job in self.jobs.values() if job.repository == repository and job.commit_sha == commit_sha]

    def recent(self, limit: int = 20) -> list[Job]:
        return list(self.jobs.values())[-limit:]


class InMemoryDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[str] = []

    def dispatch(self, job_id: str) -> None:
        self.dispatched.append(job_id)
