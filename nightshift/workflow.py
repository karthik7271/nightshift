from __future__ import annotations

import re

from .domain import IssueRef, Job, JobStatus, TERMINAL_STATUSES
from .ports import JobDispatcher, JobStore, PlanningAgent
from .policy import SafetyPolicy


def branch_name(issue_number: int, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    return f"nightshift/issue-{issue_number}-{slug or 'fix'}"


class NightShiftWorkflow:
    def __init__(self, store: JobStore, dispatcher: JobDispatcher, policy: SafetyPolicy, planner: PlanningAgent) -> None:
        self.store = store
        self.dispatcher = dispatcher
        self.policy = policy
        self.planner = planner

    def receive_issue_label(self, issue: IssueRef) -> tuple[Job, bool]:
        job = Job(id=issue.delivery_id, repository=issue.repository, issue_number=issue.issue_number,
                  issue_labels=tuple(sorted(issue.labels)), issue_title=issue.title, issue_body=issue.body,
                  installation_id=issue.installation_id)
        job, created = self.store.create_if_absent(job)
        if created:
            job.record("webhook_received", repository=issue.repository, issue_number=issue.issue_number)
            self.store.save(job)
            self.dispatcher.dispatch(job.id)
        return job, created

    def process_job(self, job_id: str) -> Job:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"Unknown NightShift job: {job_id}")
        return self.process(IssueRef(
            delivery_id=job.id, repository=job.repository, issue_number=job.issue_number,
            labels=frozenset(job.issue_labels), title=job.issue_title, body=job.issue_body,
            installation_id=job.installation_id,
        ))

    def process(self, issue: IssueRef) -> Job:
        job = self.store.get(issue.delivery_id)
        if job is None:
            job, _ = self.receive_issue_label(issue)
        if job.status in TERMINAL_STATUSES:
            return job

        job.status = JobStatus.QUALIFYING
        job.record("qualification_started")
        decision = self.policy.qualify(issue)
        if not decision.allowed:
            job.status = JobStatus.REJECTED_BY_POLICY
            job.policy_reason = decision.reason
            job.record("policy_rejected", reason=decision.reason)
            self.store.save(job)
            return job

        job.status = JobStatus.GATHERING_CONTEXT
        job.record("context_gathering_started")
        job.status = JobStatus.PLANNING
        plan = self.planner.plan(issue.repository, issue.issue_number, issue.title, issue.body)
        job.plan = plan
        job.record("plan_created", expected_files=list(plan.expected_files), confidence=plan.confidence)
        decision = self.policy.validate_plan(plan)
        if not decision.allowed:
            job.status = JobStatus.NEEDS_HUMAN_HELP
            job.policy_reason = decision.reason
            job.record("plan_rejected", reason=decision.reason)
        else:
            job.status = JobStatus.PATCHING
            job.branch_name = branch_name(issue.issue_number, issue.title)
            job.record("patch_authorized", branch_name=job.branch_name)
        self.store.save(job)
        return job
