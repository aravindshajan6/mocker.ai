from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import Attempt, QuizSession, Topic, User, UserStats
from ..routers.quiz import _badges, _get_stats
from ..schemas import DayActivity, HistoryRow, LeaderboardRow, StatsOut
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
                                                        QuizSession.finished_at.is_not(None)))).scalars().first()
    level, title, progress, to_next = scoring.level_for(stats.total_points)
    badges = await _badges(db, user.id, stats)
    return StatsOut(
        total_points=stats.total_points, level=level, level_title=title, level_progress=progress,
        points_to_next_level=to_next, current_streak=effective_streak(stats, day), longest_streak=stats.longest_streak,
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
