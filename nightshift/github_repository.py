"""Constrained GitHub repository actions performed as a GitHub App installation."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote
from urllib.request import Request, urlopen


class InstallationTokenProvider(Protocol):
    def token_for(self, installation_id: int) -> str: ...


class GitHubTransport(Protocol):
    def request(self, method: str, path: str, token: str, payload: dict[str, object] | None = None) -> dict[str, object]: ...


class UrllibGitHubTransport:
    def __init__(self, api_url: str = "https://api.github.com") -> None:
        self.api_url = api_url.rstrip("/")

    def request(self, method: str, path: str, token: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        request = Request(
            f"{self.api_url}{path}", method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2026-03-10",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())


@dataclass(frozen=True)
class RepositoryFile:
    path: str
    content: str
    sha: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str


class GitHubRepositoryWorkspace:
    """A deep module for the only GitHub mutations NightShift needs.

    It deliberately presents no merge, release, workflow, or dependency methods.
    """

    def __init__(self, repository: str, installation_id: int, token_provider: InstallationTokenProvider,
                 transport: GitHubTransport | None = None, base_branch: str = "main") -> None:
        self.repository = repository
        self.installation_id = installation_id
        self.token_provider = token_provider
        self.transport = transport or UrllibGitHubTransport()
        self.base_branch = base_branch

    def read_file(self, path: str, ref: str | None = None) -> RepositoryFile:
        encoded_path = quote(path, safe="/")
        suffix = f"?ref={quote(ref or self.base_branch, safe='')}"
        response = self._request("GET", f"/repos/{self.repository}/contents/{encoded_path}{suffix}")
        return RepositoryFile(
            path=path,
            content=base64.b64decode(str(response["content"]).replace("\n", "")).decode(),
            sha=str(response["sha"]),
        )

    def create_branch(self, branch: str) -> str:
        if not branch.startswith("nightshift/"):
            raise ValueError("NightShift may only create branches with the nightshift/ prefix.")
        ref = self._request("GET", f"/repos/{self.repository}/git/ref/heads/{quote(self.base_branch, safe='')}")
        sha = str(ref["object"]["sha"])
        self._request("POST", f"/repos/{self.repository}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
        return sha

    def upsert_file(self, branch: str, path: str, content: str, message: str) -> str:
        if not branch.startswith("nightshift/"):
            raise ValueError("NightShift may only write to nightshift/ branches.")
        existing = self.read_file(path, ref=branch)
        response = self._request("PUT", f"/repos/{self.repository}/contents/{quote(path, safe='/')}", {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
            "sha": existing.sha,
        })
        return str(response["commit"]["sha"])

    def open_draft_pr(self, branch: str, title: str, body: str) -> PullRequest:
        if not branch.startswith("nightshift/"):
            raise ValueError("NightShift may only open PRs from nightshift/ branches.")
        response = self._request("POST", f"/repos/{self.repository}/pulls", {
            "title": title,
            "head": branch,
            "base": self.base_branch,
            "body": body,
            "draft": True,
        })
        return PullRequest(number=int(response["number"]), url=str(response["html_url"]))

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return self.transport.request(method, path, self.token_provider.token_for(self.installation_id), payload)
