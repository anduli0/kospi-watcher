"""Persistence layer — ORM models, custom column types, and repositories.

The six Phase-1 tables (instruments, agent_runs, agent_findings, risk_decisions,
order_proposals, audit_logs) are defined in :mod:`kospi_watcher.db.models` and
created by the Alembic migration. Audit logs are append-only.
"""
