from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import Attempt, Question, Topic, User
from ..schemas import TopicOut

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
async def list_topics(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    counts = dict(
        (await db.execute(
            select(Question.topic_id, func.count()).where(Question.is_active.is_(True)).group_by(Question.topic_id)
        )).all()
    )
    # Per-user progress: distinct questions answered + accuracy per topic.
    prog_rows = (await db.execute(
        select(
            Question.topic_id,
            func.count(func.distinct(Attempt.question_id)),
            func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)),
            func.count(),
        )
        .join(Question, Question.id == Attempt.question_id)
        .where(Attempt.user_id == user.id)
        .group_by(Question.topic_id)
    )).all()
    prog = {r[0]: (r[1], r[2] or 0, r[3]) for r in prog_rows}
    topics = (await db.execute(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order))).scalars().all()
    out = []
    for t in topics:
        n = counts.get(t.id, 0)
        if n == 0:
            continue
        answered, correct, total = prog.get(t.id, (0, 0, 0))
        out.append(TopicOut(
            slug=t.slug, name=t.name, description=t.description, icon=t.icon, question_count=n,
            answered=answered, accuracy=(correct / total) if total else None,
        ))
    return out
