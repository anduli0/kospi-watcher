"""Load :class:`RiskLimits` from ``config/risk_limits.yml``.

Resolution order: an explicit path, then ``<cwd>/config/risk_limits.yml``, then
the repo-root copy relative to this file (works for the editable install).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from kospi_watcher.domain.risk.schemas import RiskLimits

_REL = ("config", "risk_limits.yml")


def _candidate_paths() -> list[Path]:
    return [
        Path.cwd().joinpath(*_REL),
        Path(__file__).resolve().parents[4].joinpath(*_REL),
    ]


def default_risk_limits_path() -> Path:
    for candidate in _candidate_paths():
        if candidate.exists():
            return candidate
    return _candidate_paths()[0]


def load_risk_limits(path: Path | str | None = None) -> RiskLimits:
    resolved = Path(path) if path is not None else default_risk_limits_path()
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    return RiskLimits.model_validate(data)
