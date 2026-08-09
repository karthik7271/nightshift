# NightShift

NightShift is a bounded autonomous maintenance engineer. When a GitHub issue is labelled `agent-ready` and `bug`, it qualifies the work, builds a constrained patch plan, and records a durable job for an agent worker to complete. It will only ever open a draft PR; merge authority stays with a human.

## Current vertical slice

- GitHub webhook HMAC verification
- Idempotent issue-job creation
- Explicit policy gate for labels, repository, paths, and risky files
- Durable workflow state model with an in-memory adapter for local development
- GitHub and planner seams, with deterministic local adapters for verification
- A minimal WSGI webhook endpoint suitable for a Cloud Run container

## Run locally

```bash
python -m unittest discover -s tests -v
WEBHOOK_SECRET=dev-secret python -m nightshift.app
```

Then post a signed `issues.labeled` GitHub webhook to `http://localhost:8080/webhooks/github`.

## Required cloud integrations (next)

The workflow is intentionally independent of vendor SDKs. Production adapters will provide:

- GitHub App authentication and GitHub REST actions
- Gemini via Vertex AI and Google ADK
- Firestore job storage
- Pub/Sub dispatch and Cloud Run worker execution
- Secret Manager-backed credentials

