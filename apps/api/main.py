"""Entry point for the `api` service.

Run from the repo root:
    .venv\\Scripts\\python -m uvicorn main:app --app-dir apps/api --port 8000
"""

from kospi_watcher.api.app import app

__all__ = ["app"]
