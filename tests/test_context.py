import unittest

from nightshift.agent import BoundedContextRetriever
from nightshift.domain import IssueRef


class File:
    def __init__(self, content): self.content = content


class Workspace:
    def __init__(self): self.reads = []
    def list_files(self):
        return ("src/search.py", "tests/test_search.py", "src/auth.py", "infra/main.tf", "nightshift/ui.py")
    def read_file(self, path):
        self.reads.append(path)
        return File("x" * 5_000 if path == "src/search.py" else f"content:{path}")


class ContextRetrieverTests(unittest.TestCase):
    def test_reads_only_eligible_bounded_files_and_prioritizes_issue_match(self) -> None:
        workspace = Workspace()
        issue = IssueRef("d", "o/r", 1, frozenset(), "Search crashes", "Search is empty")
        context = BoundedContextRetriever().retrieve(issue, workspace)
        self.assertEqual(("tests/test_search.py", "src/search.py", "nightshift/ui.py"), tuple(context.files))
        self.assertEqual(3, context.candidate_count)
        self.assertNotIn("src/auth.py", workspace.reads)
        self.assertNotIn("infra/main.tf", workspace.reads)
        self.assertIn("[NightShift context truncated]", context.files["src/search.py"])
