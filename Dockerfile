FROM python:3.12-slim

WORKDIR /app
COPY nightshift ./nightshift
RUN pip install --no-cache-dir google-cloud-firestore google-cloud-pubsub google-genai cryptography

ENV PORT=8080
CMD ["python", "-m", "nightshift.app"]
