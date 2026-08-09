from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    RECEIVED = "RECEIVED"
    QUALIFYING = "QUALIFYING"
    GATHERING_CONTEXT = "GATHERING_CONTEXT"
    PLANNING = "PLANNING"
    PATCHING = "PATCHING"
    WAITING_FOR_CI = "WAITING_FOR_CI"
    REPAIRING_CI = "REPAIRING_CI"
    OPENING_DRAFT_PR = "OPENING_DRAFT_PR"
    COMPLETED = "COMPLETED"
    REJECTED_BY_POLICY = "REJECTED_BY_POLICY"
    NEEDS_HUMAN_HELP = "NEEDS_HUMAN_HELP"
    FAILED = "FAILED"


TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.REJECTED_BY_POLICY,
    JobStatus.NEEDS_HUMAN_HELP,
    JobStatus.FAILED,
}


@dataclass(frozen=True)
class IssueRef:
    delivery_id: str
    repository: str
    issue_number: int
    labels: frozenset[str]
    title: str
    body: str
    installation_id: int | None = None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PatchPlan:
    summary: str
    expected_files: tuple[str, ...]
    test_command: str
    confidence: float
    risks: tuple[str, ...] = ()


@dataclass
class Job:
    id: str
    repository: str
    issue_number: int
    status: JobStatus = JobStatus.RECEIVED
    branch_name: str | None = None
    attempt: int = 0
    policy_reason: str | None = None
    plan: PatchPlan | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, **details: Any) -> None:
        self.audit_events.append({"event": event, **details})
