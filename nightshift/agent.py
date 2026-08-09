from __future__ import annotations

from .domain import PatchPlan


class DeterministicPlanner:
    """Local development adapter; replace with a Gemini + ADK adapter in production."""

    def plan(self, repository: str, issue_number: int, title: str, body: str) -> PatchPlan:
        return PatchPlan(
            summary=f"Investigate issue #{issue_number}: {title}",
            expected_files=("src/search.py", "tests/test_search.py"),
            test_command="python -m unittest discover -s tests -v",
            confidence=0.9,
        )

