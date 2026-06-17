"""Execution Gateway — the ONLY service permitted to submit broker orders.

Isolated from the Agent Service (spec §2.5/§2.6). It is allowed to import the
broker order path; the Agent Service is not. Live execution is disabled in this
phase, so the gateway only ever talks to the mock broker.
"""
