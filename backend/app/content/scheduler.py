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
from .current_affairs import day_health, run_daily, should_run_now
from .reminders import consume_telegram_links, run as run_reminders
from .verify import run_audit

log = logging.getLogger("scheduler")


def _next_run(now: datetime, hour: int) -> datetime:
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def _run_once(trigger: str) -> None:
    log.info("current-affairs job starting (%s)", trigger)
    try:
        async with SessionLocal() as db:
            run = await run_daily(db, trigger=trigger)
            log.info("current-affairs attempt %d finished: %s — %s", run.attempt, run.status, run.message)
            if run.status == "error":
                health = await day_health(db)
                if health.exhausted:
                    await notify_admins_of_failure(db, health)
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
    """Supervise the daily pull.

    Rather than firing once at 06:00 and hoping, this ticks every few minutes and asks whether the
    day still needs a run. That makes it self-healing: a failed attempt is retried on a backoff, a
    restart picks up where it left off, and a container that was down at 06:00 catches up as soon
    as it starts.
    """
    if not settings.current_affairs_enabled:
        log.info("current-affairs scheduler disabled")
        return
    await asyncio.sleep(5)  # let the app finish booting / seeding
    logged = ""
    while True:
        try:
            async with SessionLocal() as db:
                due, why = await should_run_now(db, datetime.now(IST))
            if due:
                await _run_once("scheduled" if "first attempt" in why else "retry")
            elif why != logged:
                log.info("current-affairs: %s", why)   # only log when the reason changes
                logged = why
        except Exception:  # noqa: BLE001 — a bad tick must not kill the supervisor
            log.exception("current-affairs supervisor tick failed")
        await asyncio.sleep(settings.current_affairs_tick_minutes * 60)


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


async def reminder_loop() -> None:
    """Every 15 minutes, nudge whoever asked to be nudged around now and hasn't practised."""
    if not settings.reminders_enabled:
        log.info("reminders disabled")
        return
    await asyncio.sleep(20)
    telegram_offset: int | None = None
    while True:
        try:
            async with SessionLocal() as db:
                await run_reminders(db)
                _, telegram_offset = await consume_telegram_links(db, telegram_offset)
        except Exception:  # noqa: BLE001
            log.exception("reminder pass crashed")
        await asyncio.sleep(15 * 60)


def start() -> list[asyncio.Task]:
    return [
        asyncio.create_task(loop(), name="current-affairs-scheduler"),
        asyncio.create_task(audit_loop(), name="question-audit-scheduler"),
        asyncio.create_task(reminder_loop(), name="reminder-scheduler"),
    ]


async def notify_admins_of_failure(db, health) -> None:
    """Tell the administrators when the day's pull has run out of retries.

    The app already has web push for learner reminders; an operator finding out from the admin page
    days later is worse than a single notification now.
    """
    from sqlalchemy import select

    from ..models import User
    from ..services import push

    admins = (await db.execute(select(User.id).where(User.is_admin.is_(True)))).scalars().all()
    for uid in admins:
        await push.send_to_user(db, uid, {
            "title": "Current affairs did not run",
            "body": f"{health.attempts} attempts failed for {health.day}. Last error: {health.last_message[:120]}",
            "url": "/admin",
        })
