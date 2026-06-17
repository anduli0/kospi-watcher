"""Infrastructure layer — database engine/session and the Redis/cache client.

Thin, swappable wrappers around external systems. Domain code depends on the
abstractions here, not on SQLAlchemy or redis directly where avoidable.
"""
