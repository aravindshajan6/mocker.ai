"""Stored LLM provider credentials, with failover.

Free tiers are the whole point here: they run out, get revoked, or rate-limit for a day. Keeping a
single key in the environment means a redeploy every time that happens. Instead the app holds an
ordered list of credentials in the database and walks it — a key that returns 401/403 is disabled,
one that returns 429 is put on a cooldown, and generation carries on with the next.

The environment key still works and is treated as the last resort, so nothing breaks if the table
is empty.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..content import llm
from ..models import LLMCredential

log = logging.getLogger("llm-keys")

RATE_LIMIT_COOLDOWN = timedelta(hours=6)   # free tiers usually reset on a rolling daily window


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mask(key: str) -> str:
    """Never hand a full key back to a browser, even an admin's."""
    if len(key) <= 10:
        return "•" * len(key)
    return f"{key[:6]}…{key[-4:]}"


async def usable(db: AsyncSession) -> list[LLMCredential]:
    """Active credentials that are not cooling down, best first."""
    rows = (await db.execute(
        select(LLMCredential).where(LLMCredential.is_active.is_(True))
        .order_by(LLMCredential.priority, LLMCredential.id)
    )).scalars().all()
    now = _now()
    return [c for c in rows if not c.cooldown_until or c.cooldown_until <= now]


def to_config(cred: LLMCredential) -> llm.LLMConfig:
    base, default_model = llm.PROVIDERS.get(cred.provider, ("", ""))
    return llm.LLMConfig(
        provider=cred.provider,
        api_key=cred.api_key,
        model=cred.model or default_model,
        base_url=cred.base_url or base,
    )


async def configs(db: AsyncSession, model_override: str = "") -> list[llm.LLMConfig]:
    """Every config worth trying, in order, ending with whatever the environment provides."""
    out: list[llm.LLMConfig] = []
    for cred in await usable(db):
        cfg = to_config(cred)
        if model_override:
            cfg = llm.LLMConfig(cfg.provider, cfg.api_key, model_override, cfg.base_url)
        out.append(cfg)
    env = llm.current_config()
    if env.available and not any(c.api_key == env.api_key for c in out):
        out.append(llm.LLMConfig(env.provider, env.api_key, model_override or env.model, env.base_url))
    return out


async def record_success(db: AsyncSession, cfg: llm.LLMConfig) -> None:
    cred = (await db.execute(select(LLMCredential).where(LLMCredential.api_key == cfg.api_key))).scalar_one_or_none()
    if cred:
        cred.last_used_at = _now()
        cred.last_error = None
        cred.cooldown_until = None
        await db.commit()


async def record_failure(db: AsyncSession, cfg: llm.LLMConfig, error: str) -> None:
    """Disable a rejected key; rest a rate-limited one. Anything else is just noted."""
    cred = (await db.execute(select(LLMCredential).where(LLMCredential.api_key == cfg.api_key))).scalar_one_or_none()
    if not cred:
        return
    cred.last_error = error[:500]
    cred.last_error_at = _now()
    if "HTTP 401" in error or "HTTP 403" in error:
        cred.is_active = False
        log.warning("disabled credential %s (%s): rejected by the provider", cred.id, cred.label)
    elif "rate limited" in error or "HTTP 429" in error:
        cred.cooldown_until = _now() + RATE_LIMIT_COOLDOWN
        log.info("credential %s (%s) rate limited; resting until %s", cred.id, cred.label, cred.cooldown_until)
    await db.commit()


async def complete_json_failover(db: AsyncSession, system: str, user: str, *, max_tokens: int = 2000,
                                 model_override: str = "") -> tuple[dict, llm.LLMConfig]:
    """Ask each usable credential in turn until one answers. Raises if none can."""
    import asyncio

    candidates = await configs(db, model_override)
    if not candidates:
        raise llm.LLMError("no API key configured")
    from . import budget

    last: Exception | None = None
    for cfg in candidates:
        usage: dict = {}
        try:
            data = await asyncio.to_thread(llm.complete_json, system, user, max_tokens=max_tokens,
                                           cfg=cfg, usage=usage)
        except llm.LLMError as e:
            last = e
            await record_failure(db, cfg, str(e))
            continue
        await record_success(db, cfg)
        await budget.record(db, cfg, usage)
        return data, cfg
    raise last or llm.LLMError("every configured key failed")
