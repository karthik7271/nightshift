"""Durable, dependency-free operational metrics derived from job audit events."""
from __future__ import annotations

from datetime import datetime

from .domain import Job


def _event_time(job: Job, name: str) -> datetime | None:
    for event in job.audit_events:
        if event.get("event") != name or not event.get("occurred_at"):
            continue
        try:
            return datetime.fromisoformat(str(event["occurred_at"]))
        except ValueError:
            return None
    return None


def workflow_metrics(jobs: list[Job]) -> dict[str, int | float | None]:
    """Return a small, explainable metric set over the supplied durable jobs."""
    received = len(jobs)
    decisions = [job for job in jobs if any(event.get("event") in {"policy_rejected", "policy_accepted"}
                                            for event in job.audit_events)]
    accepted = sum(any(event.get("event") == "policy_accepted" for event in job.audit_events) for job in decisions)
    ci_results = [job for job in jobs if any(event.get("event") in {"ci_passed", "ci_failed"}
                                              for event in job.audit_events)]
    ci_passed = sum(any(event.get("event") == "ci_passed" for event in job.audit_events) for job in ci_results)
    draft_durations = []
    for job in jobs:
        start, draft = _event_time(job, "webhook_received"), _event_time(job, "draft_pr_opened")
        if start and draft and draft >= start:
            draft_durations.append((draft - start).total_seconds())
    return {
        "received_jobs": received,
        "policy_decisions": len(decisions),
        "accepted_jobs": accepted,
        "acceptance_rate": round(accepted / len(decisions) * 100, 1) if decisions else None,
        "ci_results": len(ci_results),
        "ci_passed": ci_passed,
        "ci_pass_rate": round(ci_passed / len(ci_results) * 100, 1) if ci_results else None,
        "draft_pr_count": len(draft_durations),
        "avg_time_to_draft_pr_seconds": round(sum(draft_durations) / len(draft_durations), 1) if draft_durations else None,
    }
