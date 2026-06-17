"""Analysis-agent domain.

Defines the versioned ``AgentFinding`` / ``Evidence`` schemas, the agent
``Protocol``, deterministic mock agents, and the 21-agent registry. **These
modules perform analysis only and must never import the broker order path.** A
test (``tests/security/test_agent_no_submit_order.py``) statically asserts that
no module under this package references ``submit_order``.
"""

from kospi_watcher.domain.agents.schemas import (
    AGENT_FINDING_SCHEMA_VERSION,
    AgentFinding,
    AgentRun,
    AgentRunStatus,
    Evidence,
)

__all__ = [
    "AGENT_FINDING_SCHEMA_VERSION",
    "AgentFinding",
    "AgentRun",
    "AgentRunStatus",
    "Evidence",
]
