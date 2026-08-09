import unittest

from nightshift.agent import DeterministicPlanner
from nightshift.domain import IssueRef, JobStatus
from nightshift.policy import SafetyPolicy
from nightshift.store import InMemoryDispatcher, InMemoryJobStore
from nightshift.workflow import NightShiftWorkflow


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryJobStore()
        self.dispatcher = InMemoryDispatcher()
        self.workflow = NightShiftWorkflow(
            self.store, self.dispatcher,
            SafetyPolicy(approved_repositories=frozenset({"demo-org/demo-repo"})),
            DeterministicPlanner(),
        )
        self.issue = IssueRef("delivery-1", "demo-org/demo-repo", 42, frozenset({"bug", "agent-ready"}), "Empty search crashes", "")

    def test_delivery_is_idempotent(self) -> None:
        _, created = self.workflow.receive_issue_label(self.issue)
        _, duplicate = self.workflow.receive_issue_label(self.issue)
        self.assertTrue(created)
        self.assertFalse(duplicate)
        self.assertEqual(["delivery-1"], self.dispatcher.dispatched)

    def test_eligible_issue_reaches_patching(self) -> None:
        self.workflow.receive_issue_label(self.issue)
        job = self.workflow.process(self.issue)
        self.assertEqual(JobStatus.PATCHING, job.status)
        self.assertEqual("nightshift/issue-42-empty-search-crashes", job.branch_name)

    def test_worker_can_resume_job_by_id(self) -> None:
        self.workflow.receive_issue_label(self.issue)
        self.assertEqual(JobStatus.PATCHING, self.workflow.process_job("delivery-1").status)

    def test_ineligible_issue_is_rejected(self) -> None:
        issue = IssueRef("delivery-2", "demo-org/demo-repo", 43, frozenset({"bug"}), "Bug", "")
        self.workflow.receive_issue_label(issue)
        job = self.workflow.process(issue)
        self.assertEqual(JobStatus.REJECTED_BY_POLICY, job.status)

    def test_successful_ci_marks_matching_draft_complete(self) -> None:
        self.workflow.receive_issue_label(self.issue)
        job = self.store.get("delivery-1")
        job.status, job.commit_sha = JobStatus.WAITING_FOR_CI, "abc123"
        self.store.save(job)
        self.assertEqual(1, self.workflow.record_ci_result("demo-org/demo-repo", "abc123", "success"))
        self.assertEqual(JobStatus.COMPLETED, self.store.get("delivery-1").status)

    def test_failed_ci_requires_human_review(self) -> None:
        self.workflow.receive_issue_label(self.issue)
        job = self.store.get("delivery-1")
        job.status, job.commit_sha = JobStatus.WAITING_FOR_CI, "abc123"
        self.store.save(job)
        self.workflow.record_ci_result("demo-org/demo-repo", "abc123", "failure")
        self.assertEqual(JobStatus.NEEDS_HUMAN_HELP, self.store.get("delivery-1").status)
