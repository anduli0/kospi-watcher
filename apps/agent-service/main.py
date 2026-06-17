"""Entry point for the isolated `agent-service`.

Run:
    .venv\\Scripts\\python -m uvicorn main:app --app-dir apps/agent-service --port 8001
"""

from kospi_watcher.agent_service.app import app

__all__ = ["app"]
