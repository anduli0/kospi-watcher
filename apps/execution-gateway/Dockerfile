# syntax=docker/dockerfile:1
# KOSPI-WATCHER isolated `execution-gateway` (no public submit endpoint).
# Build from the REPO ROOT: docker build -f apps/execution-gateway/Dockerfile .
# NOTE: image builds are NOT verified in this phase (no Docker available locally).
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[prod]"

COPY config ./config
COPY apps/execution-gateway ./apps/execution-gateway

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8002
CMD ["python", "-m", "uvicorn", "main:app", \
     "--app-dir", "apps/execution-gateway", "--host", "0.0.0.0", "--port", "8002"]
