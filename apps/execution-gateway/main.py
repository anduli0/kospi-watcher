"""Entry point for the isolated `execution-gateway`.

Run:
    .venv\\Scripts\\python -m uvicorn main:app --app-dir apps/execution-gateway --port 8002
"""

from kospi_watcher.execution_gateway.app import app

__all__ = ["app"]
