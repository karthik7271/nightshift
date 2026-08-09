import base64
import unittest

from nightshift.github_repository import GitHubRepositoryWorkspace


class FakeTokenProvider:
    def token_for(self, installation_id: int) -> str:
        return "installation-token"


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, path, token, payload=None):
        self.calls.append((method, path, token, payload))
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "base-sha"}}
        if "/git/trees/main?recursive=1" in path:
            return {"tree": [{"path": "nightshift/app.py", "type": "blob"}, {"path": "docs", "type": "tree"}]}
        if "/contents/" in path and method == "GET":
            return {"content": base64.b64encode(b"old content").decode(), "sha": "file-sha"}
        if path.endswith("/git/refs"):
            return {"ref": "refs/heads/nightshift/issue-1-fix"}
        if "/contents/" in path and method == "PUT":
            return {"commit": {"sha": "commit-sha"}}
        if path.endswith("/pulls"):
            return {"number": 7, "html_url": "https://github.com/demo/pr/7"}
        raise AssertionError((method, path))


class GitHubRepositoryWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport()
        self.workspace = GitHubRepositoryWorkspace(
            "demo-org/demo-repo", 42, FakeTokenProvider(), self.transport
        )

    def test_creates_prefixed_branch_from_main(self) -> None:
        self.assertEqual("base-sha", self.workspace.create_branch("nightshift/issue-1-fix"))
        self.assertEqual("POST", self.transport.calls[-1][0])
        self.assertEqual({"ref": "refs/heads/nightshift/issue-1-fix", "sha": "base-sha"}, self.transport.calls[-1][3])

    def test_writes_only_to_nightshift_branch(self) -> None:
        sha = self.workspace.upsert_file("nightshift/issue-1-fix", "src/app.py", "new content", "fix: issue 1")
        self.assertEqual("commit-sha", sha)
        self.assertEqual("PUT", self.transport.calls[-1][0])
        self.assertRaises(ValueError, self.workspace.upsert_file, "main", "src/app.py", "x", "nope")

    def test_creates_draft_pr_only(self) -> None:
        pr = self.workspace.open_draft_pr("nightshift/issue-1-fix", "Fix #1", "Summary")
        self.assertEqual(7, pr.number)
        self.assertTrue(self.transport.calls[-1][3]["draft"])
        self.assertRaises(ValueError, self.workspace.open_draft_pr, "main", "No", "No")

    def test_lists_only_files_for_planning(self) -> None:
        self.assertEqual(("nightshift/app.py",), self.workspace.list_files())
