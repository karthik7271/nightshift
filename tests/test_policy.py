import unittest

from nightshift.domain import IssueRef, PatchPlan
from nightshift.policy import SafetyPolicy


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = SafetyPolicy(approved_repositories=frozenset({"demo-org/demo-repo"}))
        self.issue = IssueRef("d1", "demo-org/demo-repo", 42, frozenset({"bug", "agent-ready"}), "Empty state crashes", "")

    def test_qualifies_labeled_issue_in_approved_repository(self) -> None:
        self.assertTrue(self.policy.qualify(self.issue).allowed)

    def test_rejects_missing_label(self) -> None:
        issue = IssueRef("d1", "demo-org/demo-repo", 42, frozenset({"bug"}), "Bug", "")
        self.assertFalse(self.policy.qualify(issue).allowed)

    def test_rejects_sensitive_path(self) -> None:
        plan = PatchPlan("fix", ("src/auth/session.py",), "pytest", 0.9)
        self.assertFalse(self.policy.validate_plan(plan).allowed)

    def test_accepts_bounded_plan(self) -> None:
        plan = PatchPlan("fix", ("src/search.py", "tests/test_search.py"), "pytest", 0.9)
        self.assertTrue(self.policy.validate_plan(plan).allowed)

