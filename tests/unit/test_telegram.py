"""Telegram sender: graceful skip when unconfigured; offline success path."""

from __future__ import annotations

import httpx

from kospi_watcher.infrastructure import telegram


async def test_send_skips_when_unconfigured() -> None:
    # No TELEGRAM_* set in the test env -> never raises, returns not-ok.
    result = await telegram.send_telegram_message("hello")
    assert result.ok is False
    assert "not configured" in result.detail


async def test_send_success_with_injected_transport(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Configure creds and stub the HTTP layer so no real network call happens.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    from kospi_watcher.config import get_settings

    get_settings.cache_clear()

    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, *a: object, **k: object) -> None: ...
        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *a: object) -> None: ...
        async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
            captured["url"] = url
            captured["json"] = json
            return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(telegram.httpx, "AsyncClient", _Client)
    result = await telegram.send_telegram_message("<b>hi</b>")
    assert result.ok is True
    assert "test-token" in str(captured["url"])
    get_settings.cache_clear()
