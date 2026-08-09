import unittest
from urllib.error import HTTPError

from nightshift.github_app import GitHubAppAuthenticator, GitHubAppConfigurationError


class GitHubAppAuthenticatorTests(unittest.TestCase):
    def test_requires_client_id(self) -> None:
        with self.assertRaises(GitHubAppConfigurationError):
            GitHubAppAuthenticator("", ".secrets/key.pem")

    def test_missing_private_key_is_reported_before_network_call(self) -> None:
        authenticator = GitHubAppAuthenticator("client-id", ".secrets/missing.pem")
        with self.assertRaisesRegex(GitHubAppConfigurationError, "private key"):
            authenticator.token_for(123)

    def test_repository_name_is_required_for_installation_discovery(self) -> None:
        authenticator = GitHubAppAuthenticator("client-id", ".secrets/missing.pem")
        with self.assertRaisesRegex(GitHubAppConfigurationError, "owner/name"):
            authenticator.installation_id_for("not-a-repository")

    def test_missing_installation_has_clear_error(self) -> None:
        class MissingInstallationAuthenticator(GitHubAppAuthenticator):
            def _app_jwt(self) -> str:
                return "test-jwt"

            def _request_json(self, *args, **kwargs):
                error = HTTPError("https://api.github.com", 404, "Not Found", {}, None)
                error.close()
                raise error

        authenticator = MissingInstallationAuthenticator("client-id", ".secrets/missing.pem")
        with self.assertRaisesRegex(GitHubAppConfigurationError, "not installed"):
            authenticator.installation_id_for("demo-org/demo-repo")
