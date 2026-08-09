import unittest

from nightshift.adk_agent import PLANNER_INSTRUCTION, validate_change_scope


class AdkAgentTests(unittest.TestCase):
    def test_instruction_prohibits_merging(self) -> None:
        self.assertIn("do not merge", PLANNER_INSTRUCTION.lower())

    def test_scope_tool_accepts_bounded_source_and_test_change(self) -> None:
        result = validate_change_scope('["src/search.py", "tests/test_search.py"]', 0.9)
        self.assertTrue(result["allowed"])

    def test_scope_tool_rejects_authentication_path(self) -> None:
        result = validate_change_scope('["src/auth.py"]', 0.9)
        self.assertFalse(result["allowed"])
