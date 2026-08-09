"""Bounded patch execution from an approved plan to a draft pull request."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .domain import IssueRef, Job, JobStatus
from .github_repository import GitHubRepositoryWorkspace
from .policy import SafetyPolicy


@dataclass(frozen=True)
class FileChange:
    path: str
    content: str


class PatchAuthor(Protocol):
    def author(self, issue: IssueRef, files: dict[str, str], expected_files: tuple[str, ...]) -> tuple[FileChange, ...]: ...


class GitHubPatchExecutor:
    def __init__(self, policy: SafetyPolicy, author: PatchAuthor, workspace_factory) -> None:
        self.policy, self.author, self.workspace_factory = policy, author, workspace_factory

    def execute(self, issue: IssueRef, job: Job) -> Job:
        if not job.plan or not job.branch_name or not issue.installation_id:
            job.status, job.policy_reason = JobStatus.NEEDS_HUMAN_HELP, "Missing approved plan, branch, or GitHub installation."
            job.record("execution_blocked", reason=job.policy_reason)
            return job
        workspace: GitHubRepositoryWorkspace = self.workspace_factory(issue.repository, issue.installation_id)
        originals = {path: workspace.read_file(path).content for path in job.plan.expected_files}
        changes = self.author.author(issue, originals, job.plan.expected_files)
        proposed_paths = tuple(change.path for change in changes)
        if proposed_paths != job.plan.expected_files:
            job.status, job.policy_reason = JobStatus.NEEDS_HUMAN_HELP, "Model proposed files outside the approved plan."
            job.record("execution_blocked", reason=job.policy_reason, proposed_files=list(proposed_paths))
            return job
        workspace.create_branch(job.branch_name)
        for change in changes:
            job.commit_sha = workspace.upsert_file(job.branch_name, change.path, change.content, f"fix: #{issue.issue_number} {issue.title}")
        pr = workspace.open_draft_pr(job.branch_name, f"Fix #{issue.issue_number}: {issue.title}", self._pr_body(job))
        job.pr_number, job.pr_url = pr.number, pr.url
        job.status = JobStatus.WAITING_FOR_CI
        job.record("draft_pr_opened", number=pr.number, url=pr.url, changed_files=list(proposed_paths))
        return job

    @staticmethod
    def _pr_body(job: Job) -> str:
        return f"""## NightShift summary

Autonomous bounded fix from issue #{job.issue_number}.

### Validation
- Scope confidence: {job.plan.confidence:.0%}
- Changed files: {', '.join(job.plan.expected_files)}
- Human merge required

### Safety
- No dependency, CI, infrastructure, or authentication changes
- Draft PR only; NightShift cannot merge
"""
