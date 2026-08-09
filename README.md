# NightShift

NightShift is a bounded autonomous maintenance engineer. When a GitHub issue is labelled `agent-ready` and `bug`, it qualifies the work, builds a constrained patch plan, and records a durable job for an agent worker to complete. It will only ever open a draft PR; merge authority stays with a human.

## What is live

- GitHub webhook HMAC verification
- Idempotent issue-job creation
- Explicit policy gate for labels, repository, paths, and risky files
- Firestore-backed jobs and Pub/Sub worker dispatch
- GitHub App installation tokens, constrained repository reads/writes, and draft PR creation
- Gemini 3 Flash planning and full-file patch authoring through Vertex AI
- Deterministic, bounded context retrieval: at most six eligible files and 18,000 characters of source evidence per plan
- Draft PR explanations containing the approved plan, verification command, reviewed context, risk assessment, and merge boundary
- Check Run webhook handling that records CI outcomes without granting merge authority
- Live workflow telemetry for policy acceptance, CI pass rate, and average time-to-draft-PR
- A live Cloud Run dashboard at the deployed service URL

## Run locally

```bash
python -m unittest discover -s tests -v
WEBHOOK_SECRET=dev-secret python -m nightshift.app
```

Then post a signed `issues.labeled` GitHub webhook to `http://localhost:8080/webhooks/github`.

## Architecture

GitHub delivers signed `issues.labeled` and `check_run` webhooks to Cloud Run. Eligible jobs are persisted in Firestore and dispatched through Pub/Sub. Before planning, NightShift deterministically ranks and reads no more than six policy-eligible files, capped at 18,000 characters total. A Gemini 3 Flash planner may only select existing files inside `nightshift/`, `tests/`, or `src/`; a deterministic policy enforces confidence, file-count, path, and repository restrictions before the patch executor can create a branch or draft PR. Each PR explains the approved plan and reviewed evidence, while `/api/metrics` derives operational outcomes from durable audit events. CI outcomes are attached to the corresponding job, and all merges remain human-only.

Deployment configuration for the `ailooks-sandbox` Google Cloud project is in [infra/](infra/README.md).

## GitHub App configuration

NightShift authenticates as a GitHub App installation, not as a personal access token. Configure `Issues` and `Check run` webhook events, and grant only the repository permissions needed for issue reads, contents writes, and pull-request writes. Set `GITHUB_APP_CLIENT_ID` and `GITHUB_APP_PRIVATE_KEY_PATH`; the installation ID is taken from each signed GitHub App webhook payload. Install `cryptography` with `pip install '.[github-app]'` when enabling the production adapter.
