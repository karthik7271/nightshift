import hashlib
import hmac
import io
import json
import unittest

from nightshift.agent import DeterministicPlanner
from nightshift.app import create_app
from nightshift.policy import SafetyPolicy
from nightshift.store import InMemoryDispatcher, InMemoryJobStore
from nightshift.workflow import NightShiftWorkflow


class WebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "test-secret"
        self.store = InMemoryJobStore()
        self.dispatcher = InMemoryDispatcher()
        workflow = NightShiftWorkflow(
            self.store, self.dispatcher,
            SafetyPolicy(approved_repositories=frozenset({"demo-org/demo-repo"})),
            DeterministicPlanner(),
        )
        self.app = create_app(workflow, self.secret)

    def _call(self, payload: dict, signature: str | None = None) -> tuple[str, dict]:
        body = json.dumps(payload).encode()
        signature = signature or "sha256=" + hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        result: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            result["status"] = status

        response = self.app({
            "PATH_INFO": "/webhooks/github",
            "REQUEST_METHOD": "POST",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_X_HUB_SIGNATURE_256": signature,
            "HTTP_X_GITHUB_EVENT": "issues",
            "HTTP_X_GITHUB_DELIVERY": "delivery-3",
        }, start_response)
        return result["status"], json.loads(b"".join(response))

    def test_accepts_signed_labeled_issue(self) -> None:
        status, response = self._call({
            "action": "labeled",
            "repository": {"full_name": "demo-org/demo-repo"},
            "issue": {"number": 42, "title": "Empty search crashes", "body": "", "labels": [{"name": "bug"}, {"name": "agent-ready"}]},
        })
        self.assertEqual("202 Accepted", status)
        self.assertTrue(response["created"])
        self.assertEqual(["delivery-3"], self.dispatcher.dispatched)

    def test_rejects_bad_signature(self) -> None:
        status, response = self._call({"action": "labeled", "repository": {}, "issue": {}}, "sha256=bad")
        self.assertEqual("401 Unauthorized", status)
        self.assertEqual("invalid signature", response["error"])

