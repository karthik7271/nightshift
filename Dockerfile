FROM python:3.12-slim

WORKDIR /app
COPY nightshift ./nightshift

ENV PORT=8080
CMD ["python", "-m", "nightshift.app"]
