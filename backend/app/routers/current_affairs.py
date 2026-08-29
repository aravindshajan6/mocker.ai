from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..config import settings
from ..content import llm
from ..content.current_affairs import run_daily
from ..db import SessionLocal, get_db
from ..models import Attempt, ContentRun, Question, QuizSession, Topic, User
from ..schemas import CADay, CARun, CurrentAffairsOut
from ..services.quiz import today

router = APIRouter(prefix="/api", tags=["current-affairs"])


def _run_out(r: ContentRun | None) -> CARun | None:
    if not r:
        return None
    return CARun(day=r.day, status=r.status, provider=r.provider, model=r.model, fetched=r.fetched,
                 generated=r.generated, inserted=r.inserted, message=r.message, finished_at=r.finished_at)


@router.get("/current-affairs", response_model=CurrentAffairsOut)
async def current_affairs_overview(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Last 7 days of news questions with the user's progress on each day, plus generator status."""
    day = today()
    start = day - timedelta(days=6)
    ca = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one_or_none()
    counts: dict = {}
    answered: dict = {}
    if ca is not None:
        counts = dict((await db.execute(
            select(Question.published_at, func.count()).where(Question.topic_id == ca, Question.is_active.is_(True),
                                                             Question.published_at >= start)
            .group_by(Question.published_at)
        )).all())
        answered = dict((await db.execute(
            select(Question.published_at, func.count(func.distinct(Attempt.question_id)))
            .join(Question, Question.id == Attempt.question_id)
            .where(Attempt.user_id == user.id, Question.topic_id == ca, Question.published_at >= start)
            .group_by(Question.published_at)
        )).all())
    sessions = {s.daily_date: s for s in (await db.execute(
        select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.mode == "current-affairs",
                                  QuizSession.daily_date >= start)
    )).scalars().all()}
    days = []
    for i in range(7):
        d = day - timedelta(days=i)
        s = sessions.get(d)
        days.append(CADay(day=d, count=counts.get(d, 0), answered=answered.get(d, 0), session_id=s.id if s else None,
                          finished=bool(s and s.finished_at), score=s.score if s and s.finished_at else None))
    last = (await db.execute(select(ContentRun).where(ContentRun.status != "skipped")
                             .order_by(ContentRun.started_at.desc()).limit(1))).scalars().first()
    cfg = llm.current_config()
    return CurrentAffairsOut(today=day, days=days, enabled=settings.current_affairs_enabled, provider=cfg.provider,
                             has_key=cfg.available, last_run=_run_out(last))


async def _bg_run(force: bool) -> None:
    async with SessionLocal() as db:
        await run_daily(db, force=force)


@router.post("/admin/current-affairs/run", response_model=CARun | None)
async def trigger_run(background: BackgroundTasks, force: bool = False, wait: bool = False,
                      x_admin_token: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    """Manually run the generator. Requires ADMIN_TOKEN to be set and sent as X-Admin-Token.

    By default the run happens in the background (returns null); pass ?wait=true to block and get the result.
    """
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(403, "Admin token missing or wrong")
    if wait:
        return _run_out(await run_daily(db, force=force))
    background.add_task(_bg_run, force)
    return None
