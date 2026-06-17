"""HTTP API (FastAPI) for the main `api` service.

Exposes the seven Phase-1 endpoints. The API never returns secrets and never
places a real order; ``/risk/evaluate`` runs the deterministic Risk Engine only.
"""
