FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY nightshift ./nightshift

RUN pip install --no-cache-dir ".[github-app,agent]"

ENV PORT=8080
CMD ["python", "-m", "nightshift.app"]
