"""Usage analytics for the admin panel: screen time, active users, and when people study.

Two sources, deliberately combined:
  * attempts.answered_at — every answer since launch, so active-user counts and study-hour
    patterns have full history from day one;
  * activity_buckets — foreground screen time from heartbeats, which only exists from the day
    the heartbeat shipped, but also sees people who browse without answering.

A user counts as active on a day if either source saw them. Admin accounts are excluded from
the aggregates (an operator testing the app would otherwise inflate every number) but still
appear in the per-user list.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, Integer, case, cast, distinct, extract, func, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import ActivityBucket, Attempt, QuizSession, User, UserPresence
from .quiz import IST, today


# ---------------------------------------------------------------- heartbeat ---

def credit_seconds(last_seen: datetime | None, now: datetime) -> int:
    """How much screen time one heartbeat is worth.

    A ping means "the app was visible and used during the last interval". Crediting the gap since
    the previous ping — capped at the interval — makes the total impossible to inflate: spamming
    pings earns only the real time between them, and two open tabs share one clock rather than
    doubling it. After a long absence the gap exceeds the cap, so only the window just before the
    ping counts, which is exactly the part the client vouched for.
    """
    cap = settings.heartbeat_seconds
    if last_seen is None:
        return cap
    gap = (now - last_seen).total_seconds()
    return int(max(0, min(gap, cap)))


async def record_heartbeat(db: AsyncSession, user_id: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    last = (await db.execute(
        select(UserPresence.last_seen_at).where(UserPresence.user_id == user_id)
    )).scalar_one_or_none()
    credit = credit_seconds(last, now)

    await db.execute(pg_insert(UserPresence).values(user_id=user_id, last_seen_at=now)
                     .on_conflict_do_update(index_elements=["user_id"], set_={"last_seen_at": now}))
    if credit:
        local = now.astimezone(IST)
        stmt = pg_insert(ActivityBucket).values(
            user_id=user_id, day=local.date(), hour=local.hour, seconds=credit)
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["user_id", "day", "hour"],
            set_={"seconds": ActivityBucket.seconds + stmt.excluded.seconds},
        ))
    await db.commit()
    return credit


# ---------------------------------------------------------------- admin view ---

def _ist_day(col):
    """A timestamptz column as its IST calendar date, computed in Postgres."""
    return cast(func.timezone("Asia/Kolkata", col), Date)


async def overview(db: AsyncSession, days: int = 30) -> dict:
    now_day = today()
    start = now_day - timedelta(days=days - 1)
    learners = select(User.id).where(User.is_admin.is_(False)).scalar_subquery()

    answer_day = _ist_day(Attempt.answered_at)
    # (user, day) pairs from both sources, for "active on day D".
    active_pairs = union(
        select(Attempt.user_id.label("uid"), answer_day.label("day"))
        .where(Attempt.user_id.in_(learners), answer_day >= start),
        select(ActivityBucket.user_id.label("uid"), ActivityBucket.day.label("day"))
        .where(ActivityBucket.user_id.in_(learners), ActivityBucket.day >= start, ActivityBucket.seconds > 0),
    ).subquery()

    dau = dict((await db.execute(
        select(active_pairs.c.day, func.count(distinct(active_pairs.c.uid))).group_by(active_pairs.c.day)
    )).all())

    windows = {}
    for label, d in (("today", now_day), ("week", now_day - timedelta(days=6)), ("month", start)):
        windows[label] = (await db.execute(
            select(func.count(distinct(active_pairs.c.uid))).where(active_pairs.c.day >= d)
        )).scalar_one()

    screen_by_day = dict((await db.execute(
        select(ActivityBucket.day, func.sum(ActivityBucket.seconds))
        .where(ActivityBucket.user_id.in_(learners), ActivityBucket.day >= start)
        .group_by(ActivityBucket.day)
    )).all())
    answers_by_day = dict((await db.execute(
        select(answer_day, func.count()).where(Attempt.user_id.in_(learners), answer_day >= start)
        .group_by(answer_day)
    )).all())
    joined_day = _ist_day(User.created_at)
    new_by_day = dict((await db.execute(
        select(joined_day, func.count()).where(User.is_admin.is_(False), joined_day >= start)
        .group_by(joined_day)
    )).all())

    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        series.append({
            "day": d.isoformat(),
            "active_users": int(dau.get(d, 0)),
            "screen_seconds": int(screen_by_day.get(d, 0) or 0),
            "answers": int(answers_by_day.get(d, 0)),
            "new_users": int(new_by_day.get(d, 0)),
        })

    week_start = now_day - timedelta(days=6)
    screen_week = sum(r["screen_seconds"] for r in series if r["day"] >= week_start.isoformat())
    screen_total = (await db.execute(
        select(func.coalesce(func.sum(ActivityBucket.seconds), 0)).where(ActivityBucket.user_id.in_(learners))
    )).scalar_one()

    # Study hours: answers per (IST weekday, IST hour) over the window. Answers rather than
    # screen time so the pattern has history from launch. Postgres DOW: 0 = Sunday.
    local_ts = func.timezone("Asia/Kolkata", Attempt.answered_at)
    dow = cast(extract("dow", local_ts), Integer)
    hour = cast(extract("hour", local_ts), Integer)
    heat = (await db.execute(
        select(dow, hour, func.count())
        .where(Attempt.user_id.in_(learners), answer_day >= start)
        .group_by(dow, hour)
    )).all()

    total_learners = (await db.execute(
        select(func.count()).select_from(User).where(User.is_admin.is_(False))
    )).scalar_one()
    quizzes_week = (await db.execute(
        select(func.count()).select_from(QuizSession)
        .where(QuizSession.user_id.in_(learners), QuizSession.finished_at.is_not(None),
               _ist_day(QuizSession.finished_at) >= week_start)
    )).scalar_one()

    return {
        "days": days,
        "summary": {
            "learners": int(total_learners),
            "active_today": int(windows["today"]),
            "active_week": int(windows["week"]),
            "active_month": int(windows["month"]),
            "new_month": sum(r["new_users"] for r in series),
            "screen_seconds_week": int(screen_week),
            "screen_seconds_total": int(screen_total),
            "avg_screen_seconds_week": int(screen_week / windows["week"]) if windows["week"] else 0,
            "answers_week": sum(r["answers"] for r in series if r["day"] >= week_start.isoformat()),
            "quizzes_week": int(quizzes_week),
        },
        "series": series,
        "heatmap": [{"dow": int(d), "hour": int(h), "answers": int(n)} for d, h, n in heat],
    }


async def per_user(db: AsyncSession) -> dict[str, dict]:
    """Activity columns for the accounts list, keyed by user id."""
    now_day = today()
    week_start = now_day - timedelta(days=6)
    month_start = now_day - timedelta(days=29)

    screen = (await db.execute(
        select(ActivityBucket.user_id,
               func.sum(ActivityBucket.seconds),
               func.sum(case((ActivityBucket.day >= week_start, ActivityBucket.seconds), else_=0)))
        .group_by(ActivityBucket.user_id)
    )).all()
    seen = dict((await db.execute(select(UserPresence.user_id, UserPresence.last_seen_at))).all())

    answer_day = _ist_day(Attempt.answered_at)
    active_pairs = union(
        select(Attempt.user_id.label("uid"), answer_day.label("day")).where(answer_day >= month_start),
        select(ActivityBucket.user_id.label("uid"), ActivityBucket.day.label("day"))
        .where(ActivityBucket.day >= month_start, ActivityBucket.seconds > 0),
    ).subquery()
    active_days = dict((await db.execute(
        select(active_pairs.c.uid, func.count(distinct(active_pairs.c.day))).group_by(active_pairs.c.uid)
    )).all())
    last_answer = dict((await db.execute(
        select(Attempt.user_id, func.max(Attempt.answered_at)).group_by(Attempt.user_id)
    )).all())

    out: dict[str, dict] = {}
    for uid, total, week in screen:
        out.setdefault(uid, {}).update(screen_seconds_total=int(total or 0), screen_seconds_week=int(week or 0))
    for uid, n in active_days.items():
        out.setdefault(uid, {})["active_days_month"] = int(n)
    # "Last seen" is whichever came later: the last heartbeat or the last answer (answers
    # predate the heartbeat, so older activity is still visible).
    for uid in set(seen) | set(last_answer):
        candidates = [t for t in (seen.get(uid), last_answer.get(uid)) if t is not None]
        out.setdefault(uid, {})["last_seen_at"] = max(candidates)
    return out
