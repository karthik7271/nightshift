from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Callable
from wsgiref.simple_server import make_server

from .agent import DeterministicPlanner, GeminiPlanner
from .domain import IssueRef
from .policy import SafetyPolicy
from .store import InMemoryDispatcher, InMemoryJobStore
from .workflow import NightShiftWorkflow
from .cloud import pubsub_job_id
from .cloud import FirestoreJobStore, PubSubDispatcher
from .ui import PAGE
from .github_app import GitHubAppAuthenticator
from .github_repository import GitHubRepositoryWorkspace
from .execution import GitHubPatchExecutor
from .gemini import GeminiPatchAuthor
from .metrics import workflow_metrics


def make_workflow() -> NightShiftWorkflow:
    repository = os.getenv("APPROVED_REPOSITORY", "demo-org/demo-repo")
    if os.getenv("USE_GOOGLE_CLOUD") == "1":
        from google.cloud import firestore, pubsub_v1
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        policy = SafetyPolicy(approved_repositories=frozenset({repository}))
        authenticator = GitHubAppAuthenticator(os.environ["GITHUB_APP_CLIENT_ID"], os.environ["GITHUB_APP_PRIVATE_KEY_PATH"])
        workspace_factory = lambda repo, installation: GitHubRepositoryWorkspace(repo, installation, authenticator)
        executor = GitHubPatchExecutor(policy, GeminiPatchAuthor(project), workspace_factory)
        return NightShiftWorkflow(
            store=FirestoreJobStore(firestore.Client(project=project)),
            dispatcher=PubSubDispatcher(pubsub_v1.PublisherClient(), f"projects/{project}/topics/nightshift-jobs"),
            policy=policy, planner=GeminiPlanner(project, workspace_factory), executor=executor,
        )
    return NightShiftWorkflow(
        store=InMemoryJobStore(),
        dispatcher=InMemoryDispatcher(),
        policy=SafetyPolicy(approved_repositories=frozenset({repository})),
        planner=DeterministicPlanner(),
    )


def _valid_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_app(workflow: NightShiftWorkflow, secret: str) -> Callable:
    def app(environ: dict, start_response: Callable):
        if environ.get("PATH_INFO") == "/api/jobs" and environ.get("REQUEST_METHOD") == "GET":
            jobs = getattr(workflow.store, "recent", lambda: [])()
            payload = [{"id": j.id, "issue": j.issue_title, "number": j.issue_number,
                        "status": j.status, "branch": j.branch_name, "pr_url": j.pr_url,
                        "events": j.audit_events} for j in jobs]
            start_response("200 OK", [("Content-Type", "application/json")])
            return [json.dumps(payload, default=str).encode()]
        if environ.get("PATH_INFO") == "/api/metrics" and environ.get("REQUEST_METHOD") == "GET":
            jobs = getattr(workflow.store, "recent", lambda limit=200: [])(200)
            start_response("200 OK", [("Content-Type", "application/json")])
            return [json.dumps(workflow_metrics(jobs)).encode()]
        if environ.get("PATH_INFO") == "/" and environ.get("REQUEST_METHOD") == "GET":
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [PAGE.encode()]
        if environ.get("PATH_INFO") == "/tasks/pubsub" and environ.get("REQUEST_METHOD") == "POST":
            length = int(environ.get("CONTENT_LENGTH") or 0)
            try:
                job = workflow.process_job(pubsub_job_id(json.loads(environ["wsgi.input"].read(length))))
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                start_response("400 Bad Request", [("Content-Type", "application/json")])
                return [json.dumps({"error": str(error)}).encode()]
            start_response("200 OK", [("Content-Type", "application/json")])
            return [json.dumps({"job_id": job.id, "status": job.status}).encode()]
        if environ.get("PATH_INFO") != "/webhooks/github" or environ.get("REQUEST_METHOD") != "POST":
            start_response("404 Not Found", [("Content-Type", "application/json")])
            return [b'{"error":"not found"}']
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length)
        if not _valid_signature(secret, body, environ.get("HTTP_X_HUB_SIGNATURE_256")):
            start_response("401 Unauthorized", [("Content-Type", "application/json")])
            return [b'{"error":"invalid signature"}']
        event = environ.get("HTTP_X_GITHUB_EVENT")
        payload = json.loads(body)
        if event == "check_run":
            check_run = payload.get("check_run", {})
            matched = workflow.record_ci_result(
                payload["repository"]["full_name"], str(check_run.get("head_sha", "")), check_run.get("conclusion"),
            )
            start_response("202 Accepted", [("Content-Type", "application/json")])
            return [json.dumps({"status": "ci_recorded", "matched_jobs": matched}).encode()]
        if event != "issues":
            start_response("202 Accepted", [("Content-Type", "application/json")])
            return [b'{"status":"ignored"}']
        if payload.get("action") != "labeled":
            start_response("202 Accepted", [("Content-Type", "application/json")])
            return [b'{"status":"ignored"}']
        labels = frozenset(label["name"] for label in payload["issue"].get("labels", []))
        issue = IssueRef(
            delivery_id=environ.get("HTTP_X_GITHUB_DELIVERY", "missing-delivery"),
            repository=payload["repository"]["full_name"],
            issue_number=payload["issue"]["number"],
            labels=labels,
            title=payload["issue"]["title"],
            body=payload["issue"].get("body") or "",
            installation_id=payload.get("installation", {}).get("id"),
        )
        job, created = workflow.receive_issue_label(issue)
        response = json.dumps({"job_id": job.id, "created": created, "status": job.status}).encode()
        start_response("202 Accepted", [("Content-Type", "application/json")])
        return [response]
    return app


if __name__ == "__main__":
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if not secret:
        raise SystemExit("WEBHOOK_SECRET is required.")
    port = int(os.getenv("PORT", "8080"))
    with make_server("0.0.0.0", port, create_app(make_workflow(), secret)) as server:
        print(f"NightShift webhook receiver listening on :{port}")
        server.serve_forever()
