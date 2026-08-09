#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Usage: ./infra/bootstrap.sh PROJECT_ID [REGION]}"
REGION="${2:-us-central1}"

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com

gcloud pubsub topics create nightshift-jobs --quiet 2>/dev/null || true
gcloud pubsub topics create nightshift-job-events --quiet 2>/dev/null || true

gcloud secrets create nightshift-github-app-key --replication-policy="automatic" 2>/dev/null || true
gcloud secrets create nightshift-webhook-secret --replication-policy="automatic" 2>/dev/null || true

echo "Bootstrap complete for ${PROJECT_ID} in ${REGION}."
echo "Next: add the GitHub App PEM and webhook secret to Secret Manager, then run ./infra/deploy.sh."
