# Google Cloud deployment

Target project: `ailooks-sandbox`  
Default region: `us-central1`

## Resources

- Cloud Run: signed GitHub webhook receiver and later agent worker
- Vertex AI: Gemini planning model through Google ADK
- Firestore: durable workflow jobs and audit events
- Pub/Sub: asynchronous job dispatch and status events
- Secret Manager: GitHub App private key and webhook secret

## Bootstrap

Run from the repository root:

```bash
./infra/bootstrap.sh ailooks-sandbox us-central1
```

The script enables required APIs, creates two Pub/Sub topics, and creates empty Secret Manager secrets. It deliberately does not add secret values.

## Add secret values

```bash
gcloud secrets versions add nightshift-github-app-key \
  --data-file=.secrets/nightshift-github-app.pem

openssl rand -hex 32 | gcloud secrets versions add nightshift-webhook-secret --data-file=-
```

Use the exact webhook-secret value in the GitHub App settings after deployment.

## Deploy

```bash
./infra/deploy.sh ailooks-sandbox us-central1
```

The webhook receiver is public only because GitHub must be able to reach it. It accepts one POST path and validates GitHub's `X-Hub-Signature-256` HMAC before creating any job; all other requests receive `404`.
