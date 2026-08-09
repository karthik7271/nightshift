"""Google ADK definition for NightShift's planning agent.

This module keeps the LLM's role deliberately narrow: it proposes a structured,
bounded change plan. Deterministic policy validates any proposed action before
the GitHub workspace adapter can mutate a repository.
"""

from __future__ import annotations

import json
import os

from .domain import PatchPlan
from .policy import SafetyPolicy


PLANNER_INSTRUCTION = """You are NightShift's planning agent for small maintenance fixes.
You do not merge pull requests, modify CI, edit dependencies, or change authentication.
First identify the smallest plausible fix and its regression test. Then call
validate_change_scope. Return only a JSON object with summary, expected_files,
test_command, confidence, and risks. Never output a patch until an external policy
module has approved the proposed file scope."""


def validate_change_scope(expected_files_json: str, confidence: float) -> dict[str, object]:
    """Validate a proposed JSON list of repository files against NightShift safety policy."""
    try:
        expected_files = tuple(str(path) for path in json.loads(expected_files_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"allowed": False, "reason": "expected_files_json must be a JSON list of paths."}
    policy = SafetyPolicy(approved_repositories=frozenset({"planner-only"}))
    decision = policy.validate_plan(PatchPlan("agent proposal", expected_files, "", confidence))
    return {"allowed": decision.allowed, "reason": decision.reason}


def build_planning_agent():
    """Create the ADK agent lazily so local workflow tests do not require Google SDKs."""
    try:
        from google.adk.agents import Agent
        from google.adk.models import Gemini
        from google.genai import types
    except ImportError as error:
        raise RuntimeError("Install the ADK dependency with: pip install '.[agent]'") from error
    return Agent(
        name="nightshift_planner",
        model=Gemini(
            model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
        instruction=PLANNER_INSTRUCTION,
        tools=[validate_change_scope],
    )
