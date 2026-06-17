"""Application settings (pydantic-settings).

A single ``DATABASE_URL`` switches the persistence backend: SQLite (aiosqlite)
locally / in CI, Postgres (asyncpg) in prod. Secrets are :class:`SecretStr` so
they cannot be printed or serialised by accident. The mandated trading-safety
defaults (RESEARCH / live disabled / auto disabled) must never be changed.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from kospi_watcher.domain.enums import TradingMode

# Live order execution is NOT implemented in this phase. This module-level flag
# documents that flipping the env toggles below cannot, on its own, produce a
# real broker order — the execution path simply does not exist yet.
LIVE_EXECUTION_IMPLEMENTED = False

# Paper (simulated) execution IS implemented and safe: it moves no real money
# and contacts no real broker. It only runs when TRADING_MODE=PAPER.
PAPER_EXECUTION_IMPLEMENTED = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "KOSPI-WATCHER"
    app_version: str = "0.1.0"
    server_timezone: str = "Asia/Seoul"

    # --- Persistence ---
    # SQLite by default (dockerless local mode). Postgres in prod via DATABASE_URL.
    database_url: str = "sqlite+aiosqlite:///./kospi_watcher.db"
    # Empty -> in-memory fakeredis fallback (status reported honestly at /health).
    redis_url: str = ""

    # --- Trading safety flags (mandated defaults; do not change) ---
    trading_mode: TradingMode = TradingMode.RESEARCH
    live_trading_enabled: bool = False
    auto_execution_enabled: bool = False

    # --- Agents ---
    # "mock" = deterministic offline agents; "llm" = real Anthropic-backed
    # agents (only used when ANTHROPIC_API_KEY is set; otherwise falls back to
    # mock). Default model is the latest Claude; override to a cheaper tier
    # (e.g. claude-sonnet-4-6) for high-volume runs.
    agent_runtime: str = "mock"
    agent_model: str = "claude-opus-4-8"
    agent_max_tokens: int = 2048

    # --- Market data ---
    # "yahoo" = real, keyless quotes (KOSPI/USDKRW/ETFs); "mock" = offline.
    market_data_provider: str = "yahoo"
    market_data_ttl_seconds: int = 60
    market_data_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # --- Web / HTTP ---
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Secrets (mock placeholders in Phase 0/1; never logged or returned) ---
    anthropic_api_key: SecretStr = SecretStr("")
    kis_app_key: SecretStr = SecretStr("")
    kis_app_secret: SecretStr = SecretStr("")
    kis_account_number: SecretStr = SecretStr("")
    kiwoom_app_key: SecretStr = SecretStr("")
    kiwoom_app_secret: SecretStr = SecretStr("")
    dart_api_key: SecretStr = SecretStr("")
    ecos_api_key: SecretStr = SecretStr("")
    naver_client_id: SecretStr = SecretStr("")
    naver_client_secret: SecretStr = SecretStr("")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def live_execution_armed(self) -> bool:
        """Whether the *configuration* would permit live execution.

        Requires MULTIPLE independent gates (a single env var is never enough,
        spec §2.19). Even when True, no real order can be produced in this phase
        because the execution path is not implemented (see LIVE_EXECUTION_IMPLEMENTED).
        """
        return self.live_trading_enabled and self.trading_mode in (
            TradingMode.GUARDED_LIVE,
            TradingMode.AUTO_LIVE,
        )

    @property
    def auto_execution_armed(self) -> bool:
        """Whether configuration would permit *unattended* live execution."""
        return (
            self.live_execution_armed
            and self.auto_execution_enabled
            and self.trading_mode is TradingMode.AUTO_LIVE
        )


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton (cached)."""
    return Settings()
