#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Usage: ./infra/deploy.sh PROJECT_ID [REGION]}"
REGION="${2:-us-central1}"

gcloud config set project "$PROJECT_ID"

gcloud run deploy nightshift-webhook \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "APPROVED_REPOSITORY=karthik7271/nightshift,GITHUB_APP_CLIENT_ID=Iv23li6pKOo2oVhF7q8N,GITHUB_APP_PRIVATE_KEY_PATH=/var/run/secrets/nightshift/github-app.pem,GEMINI_MODEL=gemini-3.5-flash" \
  --set-secrets "WEBHOOK_SECRET=nightshift-webhook-secret:latest,/var/run/secrets/nightshift/github-app.pem=nightshift-github-app-key:latest"

echo "Use the Cloud Run service URL plus /webhooks/github as the GitHub App webhook URL."
