# syntax=docker/dockerfile:1
# KOSPI-WATCHER `worker` service (APScheduler; no order creation in RESEARCH).
# Build from the REPO ROOT: docker build -f apps/worker/Dockerfile .
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
COPY apps/worker ./apps/worker

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

CMD ["python", "apps/worker/main.py"]
