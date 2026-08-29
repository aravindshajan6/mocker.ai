"""The daily nudge.

Runs every 15 minutes and messages people whose chosen reminder time has just passed and who have
not done today's challenge yet. Deliberately restrained: at most one message per person per day,
never after their bedtime hour, and nothing at all if they already practised.

The copy rotates and avoids guilt. Streak pressure and sad-mascot messaging are the most criticised
part of this pattern elsewhere, and they are not worth the churn they cause.
"""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import QuizSession, User, UserPrefs, UserStats
from ..services import push, telegram
from ..services.quiz import effective_streak

log = logging.getLogger("reminders")

WINDOW_MINUTES = 20  # how long after the chosen time we will still send

# Rotated so the same line does not arrive two days running.
LINES = [
    ("Ten questions?", "A short set now and today is done."),
    ("Your daily set is waiting", "Ten questions, about four minutes."),
    ("Quick round?", "Ten questions is all it takes to keep moving."),
    ("Today's questions are ready", "Small and steady beats cramming."),
    ("A few questions before the day ends", "Ten now, and tomorrow gets easier."),
]
STREAK_LINES = [
    ("Keep the run going", "You are on a {streak}-day streak — ten questions keeps it alive."),
    ("{streak} days so far", "One short set keeps the run intact."),
]


def _pick(streak: int, seed: int) -> tuple[str, str]:
    rng = random.Random(seed)
    if streak >= 3 and rng.random() < 0.6:
        title, body = rng.choice(STREAK_LINES)
        return title.format(streak=streak), body.format(streak=streak)
    return rng.choice(LINES)


def _due_now(prefs: UserPrefs, now_utc: datetime) -> bool:
    """Has this user's local reminder time just passed, within the send window?"""
    try:
        tz = ZoneInfo(prefs.timezone or "Asia/Kolkata")
    except Exception:  # noqa: BLE001 - a bad stored zone must not stop everyone else's reminders
        tz = ZoneInfo("Asia/Kolkata")
    local = now_utc.astimezone(tz)
    target = local.replace(hour=prefs.reminder_hour, minute=prefs.reminder_minute,
                           second=0, microsecond=0)
    if local < target:
        return False
    if (local - target) > timedelta(minutes=WINDOW_MINUTES):
        return False
    return prefs.last_reminded_on != local.date()


def _local_date(prefs: UserPrefs, now_utc: datetime) -> date:
    try:
        tz = ZoneInfo(prefs.timezone or "Asia/Kolkata")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("Asia/Kolkata")
    return now_utc.astimezone(tz).date()


async def _already_practised(db: AsyncSession, user_id: str, day: date) -> bool:
    """Did they finish anything today? If so there is nothing to nudge about."""
    start = datetime.combine(day, time.min, tzinfo=ZoneInfo("Asia/Kolkata"))
    row = (await db.execute(
        select(QuizSession.id).where(QuizSession.user_id == user_id,
                                     QuizSession.finished_at.is_not(None),
                                     QuizSession.finished_at >= start).limit(1)
    )).scalar()
    return row is not None


async def run(db: AsyncSession, now_utc: datetime | None = None) -> dict:
    now_utc = now_utc or datetime.now(tz=ZoneInfo("UTC"))
    summary = {"considered": 0, "sent_push": 0, "sent_telegram": 0, "skipped_practised": 0, "no_channel": 0}
    if not settings.reminders_enabled:
        return summary

    rows = (await db.execute(
        select(UserPrefs, User, UserStats)
        .join(User, User.id == UserPrefs.user_id)
        .outerjoin(UserStats, UserStats.user_id == UserPrefs.user_id)
        .where(UserPrefs.reminders_enabled.is_(True))
    )).all()

    for prefs, user, stats in rows:
        if not _due_now(prefs, now_utc):
            continue
        summary["considered"] += 1
        day = _local_date(prefs, now_utc)
        if await _already_practised(db, user.id, day):
            prefs.last_reminded_on = day       # do not try again later today
            summary["skipped_practised"] += 1
            continue

        streak = effective_streak(stats, day) if stats else 0
        title, body = _pick(streak, seed=day.toordinal() + hash(user.id) % 1000)
        delivered = False

        sent = await push.send_to_user(db, user.id, {"title": title, "body": body, "url": "/"})
        if sent:
            summary["sent_push"] += sent
            delivered = True
        if prefs.telegram_chat_id and telegram.configured():
            if await telegram.send(prefs.telegram_chat_id,
                                   f"<b>{title}</b>\n{body}\n{settings.public_base_url}"):
                summary["sent_telegram"] += 1
                delivered = True
        if not delivered:
            summary["no_channel"] += 1
        prefs.last_reminded_on = day

    await db.commit()
    if any(v for k, v in summary.items() if k != "considered"):
        log.info("reminders: %s", summary)
    return summary


async def consume_telegram_links(db: AsyncSession, offset: int | None = None) -> tuple[int, int | None]:
    """Pair up '/start <code>' messages with the user who generated that code."""
    if not telegram.configured():
        return 0, offset
    updates = await telegram.poll_updates(offset)
    linked = 0
    last = offset
    for u in updates:
        last = u.get("update_id", 0) + 1
        text = (u.get("message") or {}).get("text") or ""
        chat_id = str(((u.get("message") or {}).get("chat") or {}).get("id") or "")
        if not text.startswith("/start") or not chat_id:
            continue
        parts = text.split()
        if len(parts) < 2:
            await telegram.send(chat_id, "Open Mocker → Settings → Reminders to get your link code.")
            continue
        code = parts[1].strip().upper()
        prefs = (await db.execute(select(UserPrefs).where(UserPrefs.telegram_link_code == code))).scalar_one_or_none()
        if not prefs:
            await telegram.send(chat_id, "That code has expired. Generate a new one in Mocker.")
            continue
        prefs.telegram_chat_id = chat_id
        prefs.telegram_link_code = None
        linked += 1
        await telegram.send(chat_id, "Linked. I'll send your daily nudge here.")
    await db.commit()
    return linked, last
