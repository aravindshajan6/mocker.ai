"""In-process daily scheduler for the current-affairs generator.

Runs inside the FastAPI process (no extra container). On startup it catches up if today's batch is
missing and the configured hour has passed, then sleeps until the next run time (IST).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from ..config import settings
from ..db import SessionLocal
from ..services.quiz import IST
from .current_affairs import run_daily
from .verify import run_audit

log = logging.getLogger("scheduler")


def _next_run(now: datetime, hour: int) -> datetime:
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def _run_once(reason: str) -> None:
    log.info("current-affairs job starting (%s)", reason)
    try:
        async with SessionLocal() as db:
            await run_daily(db)
    except Exception:  # noqa: BLE001 — never let the loop die
        log.exception("current-affairs job crashed")


async def _audit_once() -> None:
    log.info("question audit starting")
    try:
        async with SessionLocal() as db:
            summary = await run_audit(db)
            log.info("question audit finished: %s", summary)
    except Exception:  # noqa: BLE001
        log.exception("question audit crashed")


async def loop() -> None:
    if not settings.current_affairs_enabled:
        log.info("current-affairs scheduler disabled")
        return
    await asyncio.sleep(5)  # let the app finish booting / seeding
    now = datetime.now(IST)
    if now.hour >= settings.current_affairs_hour_ist:
        await _run_once("startup catch-up")  # run_daily is idempotent per day, so this is safe
    while True:
        now = datetime.now(IST)
        nxt = _next_run(now, settings.current_affairs_hour_ist)
        wait = (nxt - now).total_seconds()
        log.info("next current-affairs run at %s IST (in %.0f min)", nxt.strftime("%Y-%m-%d %H:%M"), wait / 60)
        await asyncio.sleep(wait)
        await _run_once("scheduled")


async def audit_loop() -> None:
    """Nightly answer-key audit of imported questions — separate hour so the two jobs never
    compete for the same per-minute token budget."""
    if not settings.verify_enabled:
        log.info("question audit disabled")
        return
    await asyncio.sleep(30)
    while True:
        now = datetime.now(IST)
        nxt = _next_run(now, settings.verify_hour_ist)
        wait = (nxt - now).total_seconds()
        log.info("next question audit at %s IST (in %.0f min)", nxt.strftime("%Y-%m-%d %H:%M"), wait / 60)
        await asyncio.sleep(wait)
        await _audit_once()


def start() -> list[asyncio.Task]:
    return [
        asyncio.create_task(loop(), name="current-affairs-scheduler"),
        asyncio.create_task(audit_loop(), name="question-audit-scheduler"),
    ]
