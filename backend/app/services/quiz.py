"""Question selection, daily challenge generation and streak bookkeeping."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Attempt, DailyChallenge, Question, Topic, UserStats

# Indian Standard Time — the app's "day" boundary for streaks and daily challenges.
IST = timezone(timedelta(hours=5, minutes=30))

# Hand-authored questions and real exam papers are both trustworthy and carry provenance;
# bulk-imported dataset questions are only used to backfill once these run out.
CURATED_SOURCES = ("seed", "pyq")


def today() -> date:
    return datetime.now(IST).date()


async def pick_questions(db: AsyncSession, user_id: str, count: int, topic_id: int | None = None,
                         exclude_current_affairs: bool = False) -> list[int]:
    """Prefer questions the user has never attempted; fall back to least-recently answered."""
    seen_sub = select(Attempt.question_id).where(Attempt.user_id == user_id)
    base = select(Question.id).where(Question.is_active.is_(True))
    if topic_id is not None:
        base = base.where(Question.topic_id == topic_id)
    if exclude_current_affairs:
        ca = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one_or_none()
        if ca is not None:
            base = base.where(Question.topic_id != ca)
    # Hand-authored ("seed") questions carry real explanations and are fact-checked, so serve them first;
    # imported banks act as backfill once the curated pool for this selection is exhausted.
    unseen_q = base.where(Question.id.not_in(seen_sub))
    if topic_id is not None:
        slug = (await db.execute(select(Topic.slug).where(Topic.id == topic_id))).scalar_one_or_none()
        if slug == "current-affairs":
            # News questions: newest first, no curated/imported split.
            fresh = list((await db.execute(unseen_q.order_by(Question.published_at.desc(), Question.id.desc())
                                           .limit(count))).scalars().all())
            if len(fresh) >= count:
                return fresh
            ids = fresh
            return ids + await _backfill_seen(db, user_id, base, ids, count - len(ids))
    curated = list((await db.execute(unseen_q.where(Question.source.in_(CURATED_SOURCES)))).scalars().all())
    random.shuffle(curated)
    ids = curated[:count]
    if len(ids) < count:
        imported = list((await db.execute(unseen_q.where(Question.source.not_in(CURATED_SOURCES)))).scalars().all())
        random.shuffle(imported)
        ids += imported[: count - len(ids)]
    if len(ids) < count:
        ids += await _backfill_seen(db, user_id, base, ids, count - len(ids))
    return ids


async def _backfill_seen(db: AsyncSession, user_id: str, base, exclude: list[int], n: int) -> list[int]:
    """Previously answered questions, least recently answered first."""
    last = (
        select(Attempt.question_id, func.max(Attempt.answered_at).label("last"))
        .where(Attempt.user_id == user_id)
        .group_by(Attempt.question_id)
        .subquery()
    )
    q = (
        base.join(last, last.c.question_id == Question.id)
        .where(Question.id.not_in(exclude) if exclude else True)
        .order_by(last.c.last.asc())
        .limit(n)
    )
    return list((await db.execute(q)).scalars().all())


async def current_affairs_ids(db: AsyncSession, day: date) -> list[int]:
    """All news questions published on `day` (same set for every user), oldest id first."""
    ca = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one_or_none()
    if ca is None:
        return []
    return list((await db.execute(
        select(Question.id).where(Question.topic_id == ca, Question.published_at == day, Question.is_active.is_(True))
        .order_by((Question.source == "news").desc(), Question.id)  # LLM-written first, then heuristic
        .limit(settings.current_affairs_target)
    )).scalars().all())


async def daily_question_ids(db: AsyncSession, day: date) -> list[int]:
    """Same 10 questions for everyone on a given day, spread across topics."""
    existing = await db.get(DailyChallenge, day)
    if existing:
        return list(existing.question_ids)
    rng = random.Random(day.toordinal() * 7919)
    ca_id = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one_or_none()
    topics = [t for t in (await db.execute(select(Topic.id).where(Topic.is_active.is_(True)))).scalars().all()
              if t != ca_id]
    rng.shuffle(topics)
    chosen: list[int] = []
    size = settings.daily_quiz_size
    # Up to 3 fresh current-affairs questions from the last 3 days keep the challenge topical.
    if ca_id is not None:
        recent = list((await db.execute(
            select(Question.id).where(Question.topic_id == ca_id, Question.is_active.is_(True),
                                      Question.published_at >= day - timedelta(days=3))
        )).scalars().all())
        rng.shuffle(recent)
        chosen += recent[:3]
    # Round-robin over topics so the daily set is varied.
    per_topic: dict[int, list[int]] = {}
    for t in topics:
        ids = (await db.execute(select(Question.id).where(Question.topic_id == t, Question.is_active.is_(True),
                                                           Question.source.in_(CURATED_SOURCES)))).scalars().all()
        ids = list(ids)
        rng.shuffle(ids)
        per_topic[t] = ids
    i = 0
    while len(chosen) < size and any(per_topic.values()):
        t = topics[i % len(topics)]
        if per_topic[t]:
            chosen.append(per_topic[t].pop())
        i += 1
        if i > 10_000:
            break
    if chosen:
        db.add(DailyChallenge(day=day, question_ids=chosen))
        await db.commit()
    return chosen


def touch_streak(stats: UserStats, day: date) -> bool:
    """Update streak for activity on `day`. Returns True if streak was extended today."""
    if stats.last_active_date == day:
        return False
    if stats.last_active_date == day - timedelta(days=1):
        stats.current_streak += 1
    else:
        stats.current_streak = 1
    stats.last_active_date = day
    stats.longest_streak = max(stats.longest_streak, stats.current_streak)
    return True


def effective_streak(stats: UserStats, day: date) -> int:
    """Streak as it should be displayed: 0 if the user missed yesterday."""
    if stats.last_active_date is None:
        return 0
    if stats.last_active_date >= day - timedelta(days=1):
        return stats.current_streak
    return 0
