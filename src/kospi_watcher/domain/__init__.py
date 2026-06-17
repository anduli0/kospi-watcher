"""Domain layer — pure business types and rules.

This package holds framework-agnostic domain logic: enums, time/money value
helpers, agent finding schemas, the deterministic Risk Engine, and the broker /
order-execution domain. It must not depend on FastAPI, the DB session, or any
specific broker SDK.
"""
