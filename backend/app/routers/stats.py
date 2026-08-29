from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import Attempt, Question, QuizSession, ReviewCard, Topic, User, UserStats
from ..routers.quiz import _badges, _get_stats
from ..schemas import (DayActivity, HistoryRow, InsightsOut, LeaderboardRow, ReviewDueOut, StatsOut,
                       TopicInsight)
from ..services import scoring
from ..services.quiz import IST, effective_streak, today

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/stats", response_model=StatsOut)
async def my_stats(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    stats = await _get_stats(db, user.id)
    day = today()
    start = day - timedelta(days=6)
    # Activity per IST day for the last 7 days.
    day_expr = func.date(func.timezone("Asia/Kolkata", Attempt.answered_at))
    rows = (await db.execute(
        select(day_expr, func.count(), func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), func.sum(Attempt.points))
        .where(Attempt.user_id == user.id, Attempt.answered_at >= datetime.combine(start, time.min, tzinfo=IST))
        .group_by(day_expr)
    )).all()
    by_day = {r[0]: r for r in rows}
    last7 = []
    for i in range(7):
        d = start + timedelta(days=i)
        r = by_day.get(d)
        last7.append(DayActivity(day=d, answered=r[1] if r else 0, correct=(r[2] or 0) if r else 0,
                                 points=(r[3] or 0) if r else 0))
    daily = (await db.execute(select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.daily_date == day,
                                                        QuizSession.mode == "daily",
                                                        QuizSession.finished_at.is_not(None)))).scalars().first()
    month = day.strftime("%Y-%m")
    used = stats.repairs_used if stats.repairs_month == month else 0
    streak_now = effective_streak(stats, day)
    upcoming = next((m for m in scoring.MILESTONES if m > streak_now), None)
    level, title, progress, to_next = scoring.level_for(stats.total_points)
    badges = await _badges(db, user.id, stats)
    return StatsOut(
        total_points=stats.total_points, level=level, level_title=title, level_progress=progress,
        points_to_next_level=to_next, current_streak=streak_now, longest_streak=stats.longest_streak,
        repairs_left=max(0, scoring.MONTHLY_REPAIRS - used), repairs_used=used,
        best_milestone=stats.best_milestone, next_milestone=upcoming,
        questions_answered=stats.questions_answered, correct_answers=stats.correct_answers,
        accuracy=(stats.correct_answers / stats.questions_answered) if stats.questions_answered else 0.0,
        quizzes_completed=stats.quizzes_completed, last_7_days=last7, daily_done_today=daily is not None,
        daily_score_today=daily.score if daily else None, badges=badges,
        badge_meta={k: list(v) for k, v in scoring.BADGE_META.items()},
    )


@router.get("/history", response_model=list[HistoryRow])
async def my_history(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(QuizSession, Topic).outerjoin(Topic, Topic.id == QuizSession.topic_id)
        .where(QuizSession.user_id == user.id, QuizSession.finished_at.is_not(None))
        .order_by(QuizSession.finished_at.desc()).limit(20)
    )).all()
    return [HistoryRow(id=s.id, mode=s.mode, topic=t.name if t else None, topic_icon=t.icon if t else None,
                       finished_at=s.finished_at, score=s.score, correct=s.correct, total=len(s.question_ids))
            for s, t in rows]


@router.get("/leaderboard", response_model=list[LeaderboardRow])
async def leaderboard(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Weekly leaderboard (points earned in the last 7 days), top 10 plus the current user."""
    since = datetime.combine(today() - timedelta(days=6), time.min, tzinfo=IST)
    pts = (
        select(Attempt.user_id, func.sum(Attempt.points).label("pts"))
        .where(Attempt.answered_at >= since).group_by(Attempt.user_id).subquery()
    )
    rows = (await db.execute(
        select(User.id, User.name, pts.c.pts).join(pts, pts.c.user_id == User.id).order_by(pts.c.pts.desc()).limit(10)
    )).all()
    out = [LeaderboardRow(name=n, points=int(p or 0), is_me=(uid == user.id)) for uid, n, p in rows]
    if not any(r.is_me for r in out):
        mine = (await db.execute(select(func.sum(Attempt.points)).where(Attempt.user_id == user.id,
                                                                        Attempt.answered_at >= since))).scalar()
        out.append(LeaderboardRow(name=user.name, points=int(mine or 0), is_me=True))
    return out


@router.get("/review", response_model=ReviewDueOut)
async def review_queue(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """What spaced repetition says this user should revise."""
    now = datetime.now(timezone.utc)
    end_of_day = datetime.combine(today() + timedelta(days=1), time.min, tzinfo=IST)
    due_now = (await db.execute(
        select(func.count()).select_from(ReviewCard).join(Question, Question.id == ReviewCard.question_id)
        .where(ReviewCard.user_id == user.id, ReviewCard.due_at <= now, Question.is_active.is_(True))
    )).scalar_one()
    due_today = (await db.execute(
        select(func.count()).select_from(ReviewCard).join(Question, Question.id == ReviewCard.question_id)
        .where(ReviewCard.user_id == user.id, ReviewCard.due_at <= end_of_day, Question.is_active.is_(True))
    )).scalar_one()
    learning = (await db.execute(
        select(func.count()).select_from(ReviewCard).where(ReviewCard.user_id == user.id)
    )).scalar_one()
    nxt = (await db.execute(
        select(func.min(ReviewCard.due_at)).where(ReviewCard.user_id == user.id, ReviewCard.due_at > now)
    )).scalar()
    # Retention = how often a *repeat* encounter was answered correctly in the last 30 days.
    since = now - timedelta(days=30)
    rep_rows = (await db.execute(
        select(func.count(), func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)))
        .select_from(Attempt).join(ReviewCard, (ReviewCard.user_id == Attempt.user_id) &
                                   (ReviewCard.question_id == Attempt.question_id))
        .where(Attempt.user_id == user.id, Attempt.answered_at >= since, ReviewCard.reps > 1)
    )).one()
    total_reps, correct_reps = rep_rows[0] or 0, rep_rows[1] or 0
    return ReviewDueOut(due_now=due_now, due_today=due_today, learning=learning, next_due_at=nxt,
                        retention=(correct_reps / total_reps) if total_reps >= 5 else None)


MIN_FOR_VERDICT = 8       # below this a topic's accuracy is noise, not a signal
RECENT_WINDOW = 20


@router.get("/insights", response_model=InsightsOut)
async def insights(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Where this user is strong, where they are slipping, and what is worth practising next."""
    topics = (await db.execute(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order))).scalars().all()
    counts = dict((await db.execute(
        select(Question.topic_id, func.count()).where(Question.is_active.is_(True)).group_by(Question.topic_id)
    )).all())

    # All of this user's attempts, newest first, so we can split recent from lifetime.
    rows = (await db.execute(
        select(Question.topic_id, Attempt.is_correct, Attempt.question_id, Attempt.answered_at)
        .join(Question, Question.id == Attempt.question_id)
        .where(Attempt.user_id == user.id)
        .order_by(Attempt.answered_at.desc())
    )).all()

    per: dict[int, dict] = {}
    for topic_id, ok, qid, _ in rows:
        b = per.setdefault(topic_id, {"n": 0, "ok": 0, "recent": [], "seen": set()})
        b["n"] += 1
        b["ok"] += 1 if ok else 0
        b["seen"].add(qid)
        if len(b["recent"]) < RECENT_WINDOW:
            b["recent"].append(bool(ok))

    out: list[TopicInsight] = []
    for t in topics:
        n_questions = counts.get(t.id, 0)
        if not n_questions:
            continue
        b = per.get(t.id)
        answered = b["n"] if b else 0
        correct = b["ok"] if b else 0
        acc = (correct / answered) if answered else 0.0
        recent_acc = None
        trend = "new"
        if b and len(b["recent"]) >= MIN_FOR_VERDICT:
            recent_acc = sum(b["recent"]) / len(b["recent"])
            older_n, older_ok = answered - len(b["recent"]), correct - sum(b["recent"])
            if older_n >= MIN_FOR_VERDICT:
                delta = recent_acc - (older_ok / older_n)
                trend = "improving" if delta > 0.1 else "slipping" if delta < -0.1 else "steady"
            else:
                trend = "steady"
        out.append(TopicInsight(
            slug=t.slug, name=t.name, icon=t.icon, answered=answered, correct=correct,
            accuracy=round(acc, 4), recent_accuracy=round(recent_acc, 4) if recent_acc is not None else None,
            trend=trend, coverage=round(len(b["seen"]) / n_questions, 4) if b else 0.0,
            question_count=n_questions,
        ))

    ranked = [t for t in out if t.answered >= MIN_FOR_VERDICT]
    ranked.sort(key=lambda t: (t.recent_accuracy if t.recent_accuracy is not None else t.accuracy))
    weakest = [t.slug for t in ranked[:3] if (t.recent_accuracy or t.accuracy) < 0.75]
    strongest = [t.slug for t in reversed(ranked[-3:]) if (t.recent_accuracy or t.accuracy) >= 0.75]
    untouched = [t.slug for t in out if t.answered == 0]
    answered_total = sum(t.answered for t in out)
    overall = (sum(t.correct for t in out) / answered_total) if answered_total else 0.0

    if answered_total < MIN_FOR_VERDICT * 2:
        headline = "Answer a few more questions and this page will show where you are strongest and weakest."
    elif weakest:
        names = ", ".join(next(t.name for t in out if t.slug == s) for s in weakest)
        headline = f"Your weakest ground right now: {names}. A short set on these is the fastest way to raise your score."
    elif untouched:
        headline = "Solid across everything you have tried — the biggest gains are in the topics you have not started yet."
    else:
        headline = "Strong across the board. Keep the reviews ticking over and add mock papers."

    return InsightsOut(
        topics=out, weakest=weakest, strongest=strongest, untouched=untouched,
        overall_accuracy=round(overall, 4), answered_total=answered_total,
        enough_data=answered_total >= MIN_FOR_VERDICT * 2, headline=headline,
    )
