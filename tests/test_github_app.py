import unittest

from nightshift.github_app import GitHubAppAuthenticator, GitHubAppConfigurationError


class GitHubAppAuthenticatorTests(unittest.TestCase):
    def test_requires_client_id(self) -> None:
        with self.assertRaises(GitHubAppConfigurationError):
            GitHubAppAuthenticator("", ".secrets/key.pem")

    def test_missing_private_key_is_reported_before_network_call(self) -> None:
        authenticator = GitHubAppAuthenticator("client-id", ".secrets/missing.pem")
        with self.assertRaisesRegex(GitHubAppConfigurationError, "private key"):
            authenticator.token_for(123)
