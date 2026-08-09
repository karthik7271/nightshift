"""Vertex AI Gemini adapters with JSON-only outputs."""
from __future__ import annotations
import json, os
from .execution import FileChange


class GeminiPatchAuthor:
    def __init__(self, project: str, location: str = "us-central1", model: str | None = None) -> None:
        self.project, self.location = project, location
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    def author(self, issue, files, expected_files):
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise RuntimeError("google-genai dependency is required for Gemini patching") from error
        prompt = f"""You are a bounded maintenance patch author. Issue: {issue.title}\n{issue.body}
Approved files only: {list(expected_files)}. Return JSON exactly: {{\"files\":[{{\"path\":string,\"content\":string}}]}}.
Return every approved file exactly once with its full replacement content. Do not change dependencies, CI, auth, or any unapproved path.
Current files:\n{json.dumps(files)}"""
        client = genai.Client(vertexai=True, project=self.project, location=self.location)
        response = client.models.generate_content(model=self.model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1))
        payload = json.loads(response.text)
        return tuple(FileChange(str(item["path"]), str(item["content"])) for item in payload["files"])
