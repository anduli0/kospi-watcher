"""Telegram Bot API sender (transport only).

Sends a message via ``sendMessage``. Never raises: returns a result with
``ok=False`` when Telegram is not configured or the call fails, so the caller
(the morning-briefing job) degrades safely. The bot token is a secret and is
never logged.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from kospi_watcher.config import get_settings


@dataclass(frozen=True)
class TelegramResult:
    ok: bool
    detail: str


async def send_telegram_message(text: str, *, parse_mode: str = "HTML") -> TelegramResult:
    settings = get_settings()
    token = settings.telegram_bot_token.get_secret_value()
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return TelegramResult(
            False, "telegram not configured (set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
    except httpx.HTTPError as exc:
        return TelegramResult(False, f"telegram unreachable: {type(exc).__name__}")

    if resp.status_code == 200 and resp.json().get("ok"):
        return TelegramResult(True, "sent")
    return TelegramResult(False, f"telegram error {resp.status_code}")
