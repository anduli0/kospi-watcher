# syntax=docker/dockerfile:1
# KOSPI-WATCHER `api` service. Build context is the REPO ROOT:
#   docker build -f apps/api/Dockerfile -t kospi-watcher-api .
# NOTE: image builds are NOT verified in this phase (no Docker available locally).
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Install the package (incl. asyncpg for Postgres in prod) from src-layout.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[prod]"

# Runtime assets.
COPY config ./config
COPY alembic.ini ./
COPY alembic ./alembic
COPY apps/api ./apps/api

# Drop privileges.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", \
     "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
