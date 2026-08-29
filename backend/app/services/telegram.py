"""Telegram reminders — optional, activated by setting TELEGRAM_BOT_TOKEN.

Telegram is the most reliable free channel for this audience: no per-message cost, no install
requirement beyond an app most aspirants already have, and no platform gatekeeper. The user links
their account by sending the bot a one-time code, which avoids asking for a phone number.
"""
from __future__ import annotations

import logging
import secrets

import httpx

from ..config import settings

log = logging.getLogger("telegram")


def configured() -> bool:
    return bool(settings.telegram_bot_token)


def new_link_code() -> str:
    return secrets.token_hex(4).upper()


def deep_link(code: str) -> str | None:
    if not settings.telegram_bot_username:
        return None
    return f"https://t.me/{settings.telegram_bot_username}?start={code}"


async def send(chat_id: str, text: str) -> bool:
    if not configured():
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(url, json={"chat_id": chat_id, "text": text,
                                        "parse_mode": "HTML", "disable_web_page_preview": True})
        if r.status_code != 200:
            log.warning("telegram send failed %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except httpx.HTTPError as e:
        log.warning("telegram unreachable: %s", e)
        return False


async def poll_updates(offset: int | None = None) -> list[dict]:
    """Long-poll for /start messages so users can link without a public webhook."""
    if not configured():
        return []
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    params: dict = {"timeout": 0, "allowed_updates": '["message"]'}
    if offset is not None:
        params["offset"] = offset
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, params=params)
        return r.json().get("result", []) if r.status_code == 200 else []
    except httpx.HTTPError:
        return []
