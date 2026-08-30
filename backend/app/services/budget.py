"""Daily token budget for LLM work.

Free tiers are capped on tokens per day and the API does not tell you how much is left — a 429 is
the first you hear of it, and by then the day's other jobs are also blocked. So every call records
what it cost, and bulk work asks permission before spending.

Limits are deliberately set a little under the published allowance: the reserve leaves room for the
interactive features (a learner tapping "Explain this more") after a batch job has run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..content import llm
from ..models import LLMUsage
from .quiz import today

log = logging.getLogger("budget")

# provider -> model -> tokens/day. Published free-tier caps, verified against Groq's docs.
DAILY_TOKEN_LIMITS: dict[str, dict[str, int]] = {
    "groq": {
        "openai/gpt-oss-120b": 200_000,
        "openai/gpt-oss-20b": 200_000,
        "qwen/qwen3.8-27b": 2_000_000,
        "qwen/qwen3.6-27b": 200_000,
        "_default": 200_000,
    },
    "gemini": {"_default": 1_000_000},
    "openrouter": {"_default": 100_000},
    "ollama": {"_default": 0},        # local: no cap worth enforcing
    "anthropic": {"_default": 0},     # paid: the operator sets their own limits
}

# Share of the day's allowance a batch job may consume, leaving the rest for interactive use.
BATCH_SHARE = 0.75

# Tokens per MINUTE. This is the limit bulk work actually trips: the daily allowance is generous,
# but a tight per-minute window rejects a job that simply loops as fast as it can.
MINUTE_TOKEN_LIMITS: dict[str, int] = {
    "groq": 8_000,
    "gemini": 250_000,
    "openrouter": 20_000,
}


@dataclass
class Budget:
    provider: str
    model: str
    limit: int          # 0 means "no enforced cap"
    used: int
    requests: int
    remaining: int
    batch_remaining: int
    capped: bool


def limit_for(provider: str, model: str) -> int:
    table = DAILY_TOKEN_LIMITS.get(provider, {})
    return table.get(model, table.get("_default", 0))


async def status(db: AsyncSession, provider: str, model: str, day: date | None = None) -> Budget:
    day = day or today()
    row = (await db.execute(
        select(LLMUsage).where(LLMUsage.day == day, LLMUsage.provider == provider, LLMUsage.model == model)
    )).scalar_one_or_none()
    used = row.total_tokens if row else 0
    requests = row.requests if row else 0
    limit = limit_for(provider, model)
    remaining = max(0, limit - used) if limit else 0
    return Budget(
        provider=provider, model=model, limit=limit, used=used, requests=requests,
        remaining=remaining, batch_remaining=max(0, int(limit * BATCH_SHARE) - used) if limit else 0,
        capped=bool(limit),
    )


async def record(db: AsyncSession, cfg: llm.LLMConfig, usage: dict, day: date | None = None) -> None:
    """Add one call's cost to the ledger. Never raises — accounting must not break generation."""
    total = int(usage.get("total_tokens") or 0)
    try:
        stmt = pg_insert(LLMUsage).values(
            day=day or today(), provider=cfg.provider, model=cfg.model, requests=1,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=total,
        )
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["day", "provider", "model"],
            set_={
                "requests": LLMUsage.requests + 1,
                "prompt_tokens": LLMUsage.prompt_tokens + stmt.excluded.prompt_tokens,
                "completion_tokens": LLMUsage.completion_tokens + stmt.excluded.completion_tokens,
                "total_tokens": LLMUsage.total_tokens + stmt.excluded.total_tokens,
            },
        ))
        await db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not record token usage")


async def can_spend(db: AsyncSession, cfg: llm.LLMConfig, estimate: int, *, batch: bool = True) -> tuple[bool, str]:
    """May a job spend roughly `estimate` more tokens right now?"""
    b = await status(db, cfg.provider, cfg.model)
    if not b.capped:
        return True, "no enforced cap for this provider"
    left = b.batch_remaining if batch else b.remaining
    if left <= 0:
        return False, (f"{cfg.provider}/{cfg.model}: {b.used:,} of {b.limit:,} tokens used today"
                       f"{' (batch share exhausted)' if batch else ''}")
    if estimate > left:
        return False, f"{left:,} tokens left in today's batch share, this run needs about {estimate:,}"
    return True, f"{left:,} tokens available"


async def all_budgets(db: AsyncSession) -> list[Budget]:
    """Every provider/model used today, for the admin display."""
    rows = (await db.execute(select(LLMUsage).where(LLMUsage.day == today()))).scalars().all()
    return [await status(db, r.provider, r.model) for r in rows]


class MinutePacer:
    """Keeps a batch job under the provider's tokens-per-minute ceiling.

    A rolling window rather than a fixed sleep: after a cheap batch it carries straight on, and
    after an expensive one it waits exactly long enough. Without this a loop is rate-limited within
    seconds and the run dies with most of its daily allowance untouched.
    """

    def __init__(self, provider: str, headroom: float = 0.85) -> None:
        self.limit = int(MINUTE_TOKEN_LIMITS.get(provider, 0) * headroom)
        self._events: list[tuple[float, int]] = []

    def _spent_in_window(self, now: float) -> int:
        self._events = [(t, n) for t, n in self._events if now - t < 60.0]
        return sum(n for _, n in self._events)

    async def wait_for(self, estimate: int) -> float:
        """Sleep until `estimate` more tokens fit inside the window. Returns seconds waited."""
        import asyncio
        import time

        if not self.limit:
            return 0.0
        waited = 0.0
        while True:
            now = time.monotonic()
            spent = self._spent_in_window(now)
            if spent + estimate <= self.limit or not self._events:
                return waited
            oldest = min(t for t, _ in self._events)
            sleep_for = max(1.0, 61.0 - (now - oldest))
            log.info("pacing: %d tokens used in the last minute, waiting %.0fs", spent, sleep_for)
            await asyncio.sleep(sleep_for)
            waited += sleep_for

    def record(self, tokens: int) -> None:
        import time
        self._events.append((time.monotonic(), tokens))
