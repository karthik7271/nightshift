from __future__ import annotations

import json
import os

from .domain import IssueRef, PatchPlan


class DeterministicPlanner:
    """Local development adapter; replace with a Gemini + ADK adapter in production."""

    def plan(self, issue: IssueRef) -> PatchPlan:
        return PatchPlan(
            summary=f"Investigate issue #{issue.issue_number}: {issue.title}",
            expected_files=("nightshift/ui.py",),
            test_command="python -m unittest discover -s tests -v",
            confidence=0.9,
        )


class GeminiPlanner:
    """Plans from a bounded repository tree; it cannot fetch or mutate arbitrary paths."""

    def __init__(self, project: str, workspace_factory, location: str = "us-central1", model: str | None = None) -> None:
        self.project, self.workspace_factory, self.location = project, workspace_factory, location
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    def plan(self, issue: IssueRef) -> PatchPlan:
        if not issue.installation_id:
            raise ValueError("GitHub installation ID is required to plan a repository change.")
        workspace = self.workspace_factory(issue.repository, issue.installation_id)
        candidates = tuple(path for path in workspace.list_files()
                           if path.startswith(("nightshift/", "tests/", "src/"))
                           and not any(token in path.lower() for token in ("auth", "secret", "credential", "migration")))
        if not candidates:
            raise ValueError("No policy-eligible source files found in repository.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise RuntimeError("google-genai dependency is required for Gemini planning") from error
        prompt = f"""You are NightShift's bounded maintenance planner. Create a minimal plan for this issue.
Issue #{issue.issue_number}: {issue.title}
{issue.body}
You may select at most 3 existing files only from this repository inventory: {json.dumps(candidates)}
Never select dependencies, CI, infrastructure, credentials, authentication, or migrations.
Return JSON exactly: {{"summary":string,"expected_files":[string],"test_command":string,"confidence":number,"risks":[string]}}.
Use `python -m unittest discover -s tests -v` when no narrower command is appropriate."""
        client = genai.Client(vertexai=True, project=self.project, location=self.location)
        response = client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )
        payload = json.loads(response.text)
        return PatchPlan(
            summary=str(payload["summary"]),
            expected_files=tuple(str(path) for path in payload["expected_files"]),
            test_command=str(payload["test_command"]),
            confidence=float(payload["confidence"]),
            risks=tuple(str(risk) for risk in payload.get("risks", [])),
        )
