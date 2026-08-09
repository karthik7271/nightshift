import unittest

from nightshift.domain import IssueRef, Job, JobStatus, PatchPlan
from nightshift.execution import FileChange, GitHubPatchExecutor
from nightshift.policy import SafetyPolicy


class Author:
    def author(self, issue, files, expected_files):
        return tuple(FileChange(path, files[path] + "\n# fixed") for path in expected_files)


class Workspace:
    def __init__(self): self.created = self.writes = self.pr = False
    def read_file(self, path): return type("F", (), {"content": "old"})()
    def create_branch(self, branch): self.created = True
    def upsert_file(self, *args): self.writes = True
    def open_draft_pr(self, *args): self.pr = True; return type("P", (), {"number": 8, "url": "https://example/pr/8"})()

class ExecutionTests(unittest.TestCase):
    def test_opens_draft_after_approved_file_changes(self):
        workspace = Workspace()
        executor = GitHubPatchExecutor(SafetyPolicy(frozenset({"o/r"})), Author(), lambda *_: workspace)
        job = Job("d", "o/r", 1, issue_labels=("bug","agent-ready"), issue_title="Fix", installation_id=2,
                  branch_name="nightshift/issue-1-fix", plan=PatchPlan("x", ("src/a.py",), "pytest", .9))
        issue = IssueRef("d", "o/r", 1, frozenset({"bug","agent-ready"}), "Fix", "", 2)
        self.assertEqual(JobStatus.WAITING_FOR_CI, executor.execute(issue, job).status)
        self.assertTrue(workspace.created and workspace.writes and workspace.pr)
        self.assertEqual("https://example/pr/8", job.pr_url)
