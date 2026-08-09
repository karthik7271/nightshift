"""GitHub App installation authentication.

The App private key signs a short-lived JWT. That JWT mints an installation token,
which is the only credential used for repository actions. Tokens are cached in
memory only until shortly before their expiry.
"""

from __future__ import annotations

import base64
import calendar
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class GitHubAppConfigurationError(RuntimeError):
    pass


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class InstallationToken:
    token: str
    expires_at_epoch: int

    @property
    def is_fresh(self) -> bool:
        return time.time() < self.expires_at_epoch - 60


class GitHubAppAuthenticator:
    """Mints least-privileged, one-hour GitHub installation tokens."""

    def __init__(self, client_id: str, private_key_path: str, api_url: str = "https://api.github.com") -> None:
        if not client_id:
            raise GitHubAppConfigurationError("GITHUB_APP_CLIENT_ID is required.")
        self.client_id = client_id
        self.private_key_path = Path(private_key_path)
        self.api_url = api_url.rstrip("/")
        self._tokens: dict[int, InstallationToken] = {}

    def token_for(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached and cached.is_fresh:
            return cached.token
        app_jwt = self._app_jwt()
        payload = self._request_json(
            f"/app/installations/{installation_id}/access_tokens",
            method="POST",
            token=app_jwt,
            data={"repositories": ["nightshift"]},
        )
        expires_at = time.strptime(payload["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
        minted = InstallationToken(payload["token"], calendar.timegm(expires_at))
        self._tokens[installation_id] = minted
        return minted.token

    def installation_id_for(self, repository: str) -> int:
        """Return the installation that grants this App access to one repository."""
        if "/" not in repository:
            raise GitHubAppConfigurationError("Repository must use owner/name format.")
        try:
            payload = self._request_json(
                f"/repos/{repository}/installation",
                method="GET",
                token=self._app_jwt(),
            )
        except HTTPError as error:
            if error.code == 404:
                error.close()
                raise GitHubAppConfigurationError(
                    f"The GitHub App is not installed on {repository}."
                ) from error
            raise
        try:
            return int(payload["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise GitHubAppConfigurationError(
                f"GitHub did not return an installation for {repository}."
            ) from error

    def _app_jwt(self) -> str:
        if not self.private_key_path.exists():
            raise GitHubAppConfigurationError(
                f"GitHub App private key was not found at {self.private_key_path}."
            )
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError as error:
            raise GitHubAppConfigurationError(
                "Install the GitHub App dependency with: pip install '.[github-app]'"
            ) from error
        now = int(time.time())
        header = _base64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        claims = _base64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": self.client_id}, separators=(",", ":")).encode())
        message = f"{header}.{claims}".encode("ascii")
        private_key = serialization.load_pem_private_key(self.private_key_path.read_bytes(), password=None)
        signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return f"{header}.{claims}.{_base64url(signature)}"

    def _request_json(
        self, path: str, method: str, token: str, data: dict[str, object] | None = None
    ) -> dict[str, object]:
        request = Request(
            f"{self.api_url}{path}",
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2026-03-10",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
