from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Callable
from wsgiref.simple_server import make_server

from .agent import DeterministicPlanner
from .domain import IssueRef
from .policy import SafetyPolicy
from .store import InMemoryDispatcher, InMemoryJobStore
from .workflow import NightShiftWorkflow
from .cloud import pubsub_job_id


def make_workflow() -> NightShiftWorkflow:
    repository = os.getenv("APPROVED_REPOSITORY", "demo-org/demo-repo")
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
        if environ.get("HTTP_X_GITHUB_EVENT") != "issues":
            start_response("202 Accepted", [("Content-Type", "application/json")])
            return [b'{"status":"ignored"}']
        payload = json.loads(body)
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
