"""Unauthenticated endpoints for the marketing page.

Only aggregate, non-identifying content — bank sizes and topic names — so the landing page can
quote real numbers instead of hardcoded ones that drift as the banks grow.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Question, Topic

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    counts = dict(
        (await db.execute(
            select(Question.topic_id, func.count()).where(Question.is_active.is_(True)).group_by(Question.topic_id)
        )).all()
    )
    topics = (await db.execute(
        select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order)
    )).scalars().all()
    listed = [
        {"slug": t.slug, "name": t.name, "icon": t.icon, "question_count": counts.get(t.id, 0)}
        for t in topics if counts.get(t.id, 0) > 0
    ]
    pyq = (await db.execute(
        select(func.count()).select_from(Question)
        .where(Question.is_active.is_(True), Question.source == "pyq")
    )).scalar_one()
    return {
        "questions": sum(counts.values()),
        "topics": len(listed),
        "past_paper_questions": pyq,
        "topic_list": listed,
    }
