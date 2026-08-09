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

    def test_ineligible_issue_is_rejected(self) -> None:
        issue = IssueRef("delivery-2", "demo-org/demo-repo", 43, frozenset({"bug"}), "Bug", "")
        self.workflow.receive_issue_label(issue)
        job = self.workflow.process(issue)
        self.assertEqual(JobStatus.REJECTED_BY_POLICY, job.status)

