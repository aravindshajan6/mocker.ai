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

from sqlalchemy import Date, Float, Integer, case, cast, distinct, extract, func, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import ActivityBucket, Attempt, Question, QuizSession, Topic, User, UserPresence, UserStats
from .quiz import IST, effective_streak, today


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


# ------------------------------------------------------------- full dashboard ---

STREAK_BUCKETS = [("0", 0, 0), ("1–2", 1, 2), ("3–6", 3, 6), ("7–13", 7, 13), ("14–29", 14, 29), ("30+", 30, 10**9)]
COHORT_WEEKS = 8


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())          # Monday


def _active_pairs(learners, a: date, b: date):
    """(user, IST day) pairs where the user answered or used the app, for a in..b inclusive."""
    answer_day = _ist_day(Attempt.answered_at)
    return union(
        select(Attempt.user_id.label("uid"), answer_day.label("day"))
        .where(Attempt.user_id.in_(learners), answer_day >= a, answer_day <= b),
        select(ActivityBucket.user_id.label("uid"), ActivityBucket.day.label("day"))
        .where(ActivityBucket.user_id.in_(learners), ActivityBucket.day >= a, ActivityBucket.day <= b,
               ActivityBucket.seconds > 0),
    ).subquery()


async def _window(db: AsyncSession, learners, a: date, b: date) -> dict:
    """Headline numbers for one window, plus its per-day series."""
    days = (b - a).days + 1
    pairs = _active_pairs(learners, a, b)
    active = (await db.execute(select(func.count(distinct(pairs.c.uid))))).scalar_one()
    dau = dict((await db.execute(
        select(pairs.c.day, func.count(distinct(pairs.c.uid))).group_by(pairs.c.day))).all())

    answer_day = _ist_day(Attempt.answered_at)
    ans = {d: (int(n), int(c or 0)) for d, n, c in (await db.execute(
        select(answer_day, func.count(), func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)))
        .where(Attempt.user_id.in_(learners), answer_day >= a, answer_day <= b).group_by(answer_day)
    )).all()}
    screen = dict((await db.execute(
        select(ActivityBucket.day, func.sum(ActivityBucket.seconds))
        .where(ActivityBucket.user_id.in_(learners), ActivityBucket.day >= a, ActivityBucket.day <= b)
        .group_by(ActivityBucket.day))).all())
    done_day = _ist_day(QuizSession.finished_at)
    quizzes = dict((await db.execute(
        select(done_day, func.count()).where(QuizSession.user_id.in_(learners),
                                              QuizSession.finished_at.is_not(None),
                                              done_day >= a, done_day <= b).group_by(done_day))).all())
    join_day = _ist_day(User.created_at)
    joined = dict((await db.execute(
        select(join_day, func.count()).where(User.is_admin.is_(False), join_day >= a, join_day <= b)
        .group_by(join_day))).all())

    series = []
    for i in range(days):
        d = a + timedelta(days=i)
        n, c = ans.get(d, (0, 0))
        series.append({"day": d.isoformat(), "active": int(dau.get(d, 0)), "screen_seconds": int(screen.get(d, 0) or 0),
                       "answers": n, "correct": c, "quizzes": int(quizzes.get(d, 0)), "new_users": int(joined.get(d, 0))})
    answers = sum(r["answers"] for r in series)
    correct = sum(r["correct"] for r in series)
    screen_total = sum(r["screen_seconds"] for r in series)
    return {
        "series": series,
        "totals": {
            "active": int(active),
            "avg_daily_active": round(sum(r["active"] for r in series) / days, 2),
            "screen_seconds": screen_total,
            "screen_per_active": int(screen_total / active) if active else 0,
            "answers": answers,
            "accuracy": round(correct / answers, 4) if answers else None,
            "quizzes": sum(r["quizzes"] for r in series),
            "new_users": sum(r["new_users"] for r in series),
        },
    }


async def dashboard(db: AsyncSession, days: int = 30) -> dict:
    end = today()
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    learners = select(User.id).where(User.is_admin.is_(False)).scalar_subquery()

    cur = await _window(db, learners, start, end)
    prev = await _window(db, learners, prev_start, prev_end)
    total_learners = (await db.execute(
        select(func.count()).select_from(User).where(User.is_admin.is_(False)))).scalar_one()
    # Stickiness: of everyone active in the last 30 days, the share who show up on a typical day.
    month = await _window(db, learners, end - timedelta(days=29), end)
    stickiness = (month["totals"]["avg_daily_active"] / month["totals"]["active"]) if month["totals"]["active"] else None

    answer_day = _ist_day(Attempt.answered_at)
    in_range = (Attempt.user_id.in_(learners), answer_day >= start, answer_day <= end)
    correct_n = func.sum(case((Attempt.is_correct.is_(True), 1), else_=0))

    topics = [{"name": n, "icon": i, "answers": int(a), "correct": int(c or 0), "learners": int(l)}
              for n, i, a, c, l in (await db.execute(
                  select(Topic.name, Topic.icon, func.count(), correct_n, func.count(distinct(Attempt.user_id)))
                  .join(Question, Question.id == Attempt.question_id).join(Topic, Topic.id == Question.topic_id)
                  .where(*in_range).group_by(Topic.name, Topic.icon))).all()]

    difficulty = [{"difficulty": int(d), "answers": int(a), "correct": int(c or 0)} for d, a, c in (await db.execute(
        select(Question.difficulty, func.count(), correct_n).join(Question, Question.id == Attempt.question_id)
        .where(*in_range).group_by(Question.difficulty).order_by(Question.difficulty))).all()]

    sources = [{"source": s, "answers": int(a), "correct": int(c or 0)} for s, a, c in (await db.execute(
        select(Question.source, func.count(), correct_n).join(Question, Question.id == Attempt.question_id)
        .where(*in_range).group_by(Question.source))).all()]

    start_day = _ist_day(QuizSession.started_at)
    modes = [{"mode": m, "started": int(s), "finished": int(f or 0)} for m, s, f in (await db.execute(
        select(QuizSession.mode, func.count(), func.sum(case((QuizSession.finished_at.is_not(None), 1), else_=0)))
        .where(QuizSession.user_id.in_(learners), start_day >= start, start_day <= end)
        .group_by(QuizSession.mode))).all()]

    local_ts = func.timezone("Asia/Kolkata", Attempt.answered_at)
    dow = cast(extract("dow", local_ts), Integer)
    hour = cast(extract("hour", local_ts), Integer)
    heatmap = [{"dow": int(d), "hour": int(h), "answers": int(n)} for d, h, n in (await db.execute(
        select(dow, hour, func.count()).where(*in_range).group_by(dow, hour))).all()]

    # Exams: score as a share of the paper, after negative marking — so it can dip below zero.
    done_day = _ist_day(QuizSession.finished_at)
    exam_rows = (await db.execute(
        select(QuizSession.raw_score, func.json_array_length(QuizSession.question_ids))
        .where(QuizSession.user_id.in_(learners), QuizSession.mode == "exam",
               QuizSession.finished_at.is_not(None), done_day >= start, done_day <= end))).all()
    pcts = [100 * (raw or 0) / n for raw, n in exam_rows if n]
    bins = [{"label": "<0", "count": sum(1 for p in pcts if p < 0)}]
    for lo in range(0, 100, 10):
        hi = lo + 10
        bins.append({"label": f"{lo}–{hi}", "count": sum(1 for p in pcts if lo <= p < hi or (hi == 100 and p == 100))})
    exams = {"taken": len(pcts), "avg_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
             "best_pct": round(max(pcts), 1) if pcts else None, "distribution": bins}

    # Hardest questions: lowest accuracy among questions answered at least three times.
    acc = correct_n.cast(Float) / func.count()
    hardest = [{"id": qid, "text": (t[:160] + "…") if len(t) > 160 else t, "topic": tn,
                "attempts": int(n), "accuracy": round(float(a), 4)} for qid, t, tn, n, a in (await db.execute(
        select(Question.id, Question.text, Topic.name, func.count(), acc)
        .join(Question, Question.id == Attempt.question_id).join(Topic, Topic.id == Question.topic_id)
        .where(*in_range).group_by(Question.id, Question.text, Topic.name)
        .having(func.count() >= 3).order_by(acc.asc(), func.count().desc()).limit(8))).all()]

    screen_by_user = dict((await db.execute(
        select(ActivityBucket.user_id, func.sum(ActivityBucket.seconds))
        .where(ActivityBucket.day >= start, ActivityBucket.day <= end).group_by(ActivityBucket.user_id))).all())
    top = (await db.execute(
        select(User.id, User.name, func.count(), correct_n)
        .join(Attempt, Attempt.user_id == User.id).where(*in_range)
        .group_by(User.id, User.name).order_by(func.count().desc()).limit(8))).all()
    stats_rows = {s.user_id: s for s in (await db.execute(
        select(UserStats).where(UserStats.user_id.in_(learners)))).scalars().all()}
    top_learners = [{"name": n, "answers": int(a), "accuracy": round(int(c or 0) / int(a), 4) if a else None,
                     "screen_seconds": int(screen_by_user.get(uid, 0) or 0),
                     "streak": effective_streak(stats_rows[uid], end) if uid in stats_rows else 0}
                    for uid, n, a, c in top]

    streak_counts = {label: 0 for label, _, _ in STREAK_BUCKETS}
    all_learner_ids = (await db.execute(select(User.id).where(User.is_admin.is_(False)))).scalars().all()
    for uid in all_learner_ids:
        s = effective_streak(stats_rows[uid], end) if uid in stats_rows else 0
        for label, lo, hi in STREAK_BUCKETS:
            if lo <= s <= hi:
                streak_counts[label] += 1
                break

    return {
        "range": {"days": days, "start": start.isoformat(), "end": end.isoformat()},
        "learners": int(total_learners),
        "current": cur, "previous": prev["totals"],
        "stickiness": round(stickiness, 4) if stickiness is not None else None,
        "topics": sorted(topics, key=lambda t: -t["answers"]),
        "difficulty": difficulty, "sources": sorted(sources, key=lambda s: -s["answers"]),
        "modes": sorted(modes, key=lambda m: -m["started"]),
        "heatmap": heatmap, "exams": exams, "hardest": hardest, "top_learners": top_learners,
        "streaks": [{"label": k, "users": v} for k, v in streak_counts.items()],
        "cohorts": await _cohorts(db, end),
    }


async def _cohorts(db: AsyncSession, end: date) -> list[dict]:
    """Weekly signup cohorts: the share of each cohort active in each week after joining."""
    first_week = _week_start(end) - timedelta(weeks=COHORT_WEEKS - 1)
    join_day = _ist_day(User.created_at)
    members = (await db.execute(
        select(User.id, join_day).where(User.is_admin.is_(False), join_day >= first_week))).all()
    if not members:
        return []
    ids = [uid for uid, _ in members]
    answer_day = _ist_day(Attempt.answered_at)
    pairs = (await db.execute(union(
        select(Attempt.user_id, answer_day).where(Attempt.user_id.in_(ids), answer_day >= first_week),
        select(ActivityBucket.user_id, ActivityBucket.day)
        .where(ActivityBucket.user_id.in_(ids), ActivityBucket.day >= first_week, ActivityBucket.seconds > 0),
    ))).all()
    active_weeks: dict[str, set[date]] = {}
    for uid, d in pairs:
        active_weeks.setdefault(uid, set()).add(_week_start(d))

    cohorts: dict[date, list[str]] = {}
    for uid, jd in members:
        cohorts.setdefault(_week_start(jd), []).append(uid)
    current_week = _week_start(end)
    out = []
    for week in sorted(cohorts):
        users = cohorts[week]
        cells = []
        for k in range(COHORT_WEEKS):
            wk = week + timedelta(weeks=k)
            if wk > current_week:
                break                       # that week hasn't happened yet
            cells.append(round(sum(1 for u in users if wk in active_weeks.get(u, ())) / len(users), 4))
        out.append({"week": week.isoformat(), "size": len(users), "retention": cells})
    return out
