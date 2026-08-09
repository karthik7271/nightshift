import hashlib
import hmac
import io
import json
import unittest

from nightshift.agent import DeterministicPlanner
from nightshift.app import create_app
from nightshift.domain import IssueRef, JobStatus
from nightshift.policy import SafetyPolicy
from nightshift.store import InMemoryDispatcher, InMemoryJobStore
from nightshift.workflow import NightShiftWorkflow


class WebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "test-secret"
        self.store = InMemoryJobStore()
        self.dispatcher = InMemoryDispatcher()
        self.workflow = NightShiftWorkflow(
            self.store, self.dispatcher,
            SafetyPolicy(approved_repositories=frozenset({"demo-org/demo-repo"})),
            DeterministicPlanner(),
        )
        self.app = create_app(self.workflow, self.secret)
        self.issue = IssueRef("delivery-check", "demo-org/demo-repo", 7, frozenset({"bug", "agent-ready"}), "Check result", "")

    def _call(self, payload: dict, signature: str | None = None, event: str = "issues") -> tuple[str, dict]:
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
            "HTTP_X_GITHUB_EVENT": event,
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

    def test_records_check_run_result(self) -> None:
        job, _ = self.workflow.receive_issue_label(self.issue)
        job.status, job.commit_sha = JobStatus.WAITING_FOR_CI, "deadbeef"
        self.workflow.store.save(job)
        body = json.dumps({"repository": {"full_name": "demo-org/demo-repo"},
                           "check_run": {"head_sha": "deadbeef", "conclusion": "success"}}).encode()
        status, response = self._call(json.loads(body), event="check_run")
        self.assertEqual("202 Accepted", status)
        self.assertEqual(JobStatus.COMPLETED, self.workflow.store.get(self.issue.delivery_id).status)

    def test_exposes_empty_metrics(self) -> None:
        result = {}
        response = self.app({
            "PATH_INFO": "/api/metrics", "REQUEST_METHOD": "GET",
            "CONTENT_LENGTH": "0", "wsgi.input": io.BytesIO(),
        }, lambda status, headers: result.setdefault("status", status))
        self.assertEqual("200 OK", result["status"])
        self.assertIsNone(json.loads(b"".join(response))["acceptance_rate"])
