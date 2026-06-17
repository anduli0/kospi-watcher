# syntax=docker/dockerfile:1
# KOSPI-WATCHER isolated `agent-service` (analysis only; no order authority).
# Build from the REPO ROOT: docker build -f apps/agent-service/Dockerfile .
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
COPY apps/agent-service ./apps/agent-service

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "main:app", \
     "--app-dir", "apps/agent-service", "--host", "0.0.0.0", "--port", "8001"]
