"""Exam mode — a full-length mock in the real Kerala PSC format.

Differences from the practice quiz that matter pedagogically:
  * no feedback until the paper is submitted (you cannot learn the answer mid-paper),
  * answers can be changed and questions left deliberately blank,
  * 1/3 negative marking, so knowing *when not to guess* is part of the skill,
  * a server-side deadline, so the timer cannot be gamed by editing the client clock.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import current_user
from ..db import get_db
from ..models import Attempt, Question, QuizSession, Topic, User, utcnow
from ..schemas import (ExamQuestionReview, ExamResultOut, ExamStateOut, QuestionOut, SaveAnswerIn,
                       StartExamIn)
from ..services import scoring
from ..services.quiz import effective_streak, pick_questions, today, touch_streak
from ..routers.quiz import _get_stats

router = APIRouter(prefix="/api/exam", tags=["exam"])


def _seconds_left(s: QuizSession) -> int:
    if not s.expires_at:
        return 0
    return max(0, int((s.expires_at - utcnow()).total_seconds()))


async def _load(db: AsyncSession, session_id: str, user: User) -> QuizSession:
    s = await db.get(QuizSession, session_id, options=[selectinload(QuizSession.attempts)])
    if not s or s.user_id != user.id or s.mode != "exam":
        raise HTTPException(404, "Exam not found")
    return s


async def _state(db: AsyncSession, s: QuizSession) -> ExamStateOut:
    rows = (await db.execute(select(Question, Topic).join(Topic, Topic.id == Question.topic_id)
                             .where(Question.id.in_(s.question_ids)))).all()
    by_id = {q.id: (q, t) for q, t in rows}
    questions = [QuestionOut(id=q.id, text=q.text, options=q.options, difficulty=q.difficulty,
                             topic=t.name, topic_icon=t.icon, published_at=q.published_at,
                             source_ref=q.source_ref)
                 for qid in s.question_ids if qid in by_id for q, t in [by_id[qid]]]
    return ExamStateOut(
        id=s.id, questions=questions,
        answers={a.question_id: a.selected_index for a in s.attempts},
        marked=[a.question_id for a in s.attempts if a.marked_for_review],
        seconds_remaining=_seconds_left(s), duration_seconds=s.duration_seconds or 0,
        total=len(s.question_ids), submitted=s.finished_at is not None,
    )


@router.post("/start", response_model=ExamStateOut)
async def start_exam(data: StartExamIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    # Resume an exam that is still running rather than silently starting a second one.
    running = (await db.execute(
        select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.mode == "exam",
                                  QuizSession.finished_at.is_(None))
        .options(selectinload(QuizSession.attempts)).order_by(QuizSession.started_at.desc())
    )).scalars().first()
    if running and _seconds_left(running) > 0:
        return await _state(db, running)

    topic_id = None
    if data.topic:
        t = (await db.execute(select(Topic).where(Topic.slug == data.topic))).scalar_one_or_none()
        if not t:
            raise HTTPException(404, "Unknown topic")
        topic_id = t.id
    ids = await pick_questions(db, user.id, data.count, topic_id=topic_id)
    if len(ids) < 10:
        raise HTTPException(409, "Not enough questions available for an exam yet")
    s = QuizSession(
        user_id=user.id, mode="exam", topic_id=topic_id, question_ids=ids,
        duration_seconds=data.duration_minutes * 60,
        expires_at=utcnow() + timedelta(minutes=data.duration_minutes),
        negative_marking=scoring.NEGATIVE_MARK,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s, ["attempts"])
    return await _state(db, s)


@router.get("/current", response_model=ExamStateOut | None)
async def current_exam(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """The exam still in progress, if any — so a refresh or a new device resumes it."""
    s = (await db.execute(
        select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.mode == "exam",
                                  QuizSession.finished_at.is_(None))
        .options(selectinload(QuizSession.attempts)).order_by(QuizSession.started_at.desc())
    )).scalars().first()
    if not s or _seconds_left(s) <= 0:
        return None
    return await _state(db, s)


@router.get("/{session_id}", response_model=ExamStateOut)
async def get_exam(session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await _state(db, await _load(db, session_id, user))


@router.post("/{session_id}/answer")
async def save_answer(session_id: str, data: SaveAnswerIn, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    """Record or change an answer. Deliberately returns no correctness — this is an exam."""
    s = await _load(db, session_id, user)
    if s.finished_at:
        raise HTTPException(409, "This exam has already been submitted")
    if _seconds_left(s) <= 0:
        raise HTTPException(409, "Time is up — submit the paper to see your score")
    if data.question_id not in s.question_ids:
        raise HTTPException(400, "Question is not part of this exam")
    existing = next((a for a in s.attempts if a.question_id == data.question_id), None)
    if existing:
        existing.selected_index = data.selected_index
        existing.marked_for_review = data.marked_for_review
        existing.answered_at = utcnow()
    else:
        db.add(Attempt(session_id=s.id, user_id=user.id, question_id=data.question_id,
                       selected_index=data.selected_index, is_correct=False, points=0,
                       marked_for_review=data.marked_for_review))
    await db.commit()
    answered = sum(1 for a in s.attempts if a.selected_index >= 0)
    return {"ok": True, "answered": answered, "seconds_remaining": _seconds_left(s)}


@router.post("/{session_id}/submit", response_model=ExamResultOut)
async def submit_exam(session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    s = await _load(db, session_id, user)
    rows = (await db.execute(select(Question, Topic).join(Topic, Topic.id == Question.topic_id)
                             .where(Question.id.in_(s.question_ids)))).all()
    by_id = {q.id: (q, t) for q, t in rows}
    attempts = {a.question_id: a for a in s.attempts}

    correct = wrong = blank = 0
    per_topic: dict[str, dict] = {}
    review: list[ExamQuestionReview] = []
    for n, qid in enumerate(s.question_ids, start=1):
        if qid not in by_id:
            continue
        q, t = by_id[qid]
        a = attempts.get(qid)
        chosen = a.selected_index if a and a.selected_index >= 0 else None
        is_right = chosen is not None and chosen == q.correct_index
        if chosen is None:
            blank += 1
        elif is_right:
            correct += 1
        else:
            wrong += 1
        bucket = per_topic.setdefault(t.name, {"topic": t.name, "icon": t.icon, "total": 0, "correct": 0, "wrong": 0, "blank": 0})
        bucket["total"] += 1
        bucket["correct" if is_right else ("blank" if chosen is None else "wrong")] += 1
        review.append(ExamQuestionReview(
            question_id=qid, number=n, text=q.text, options=q.options, selected_index=chosen,
            correct_index=q.correct_index, is_correct=is_right, skipped=chosen is None,
            explanation=q.explanation, topic=t.name, source_ref=q.source_ref,
        ))

    total = len(review)
    raw = scoring.exam_raw_score(correct, wrong, s.negative_marking or scoring.NEGATIVE_MARK)
    pts = scoring.exam_points(correct, wrong, total)

    if not s.finished_at:
        # Persist per-question grading so stats and the review screen agree.
        for r in review:
            a = attempts.get(r.question_id)
            if a:
                a.is_correct = r.is_correct
                a.points = 10 if r.is_correct else 0
        stats = await _get_stats(db, user.id)
        answered_now = sum(1 for r in review if not r.skipped)
        stats.questions_answered += answered_now
        stats.correct_answers += correct
        stats.total_points += pts
        stats.quizzes_completed += 1
        if answered_now:
            touch_streak(stats, today())  # exam attempts count as practice for the streak
        s.correct = correct
        s.raw_score = raw
        s.score = pts
        s.finished_at = utcnow()
        await db.commit()

    elapsed = int(((s.finished_at or utcnow()) - s.started_at).total_seconds())
    attempted = correct + wrong
    lost = round(wrong * (s.negative_marking or scoring.NEGATIVE_MARK), 2)
    be = scoring.guess_break_even(4, s.negative_marking or scoring.NEGATIVE_MARK)
    if wrong == 0 and blank > 0:
        coaching = (f"You left {blank} blank and got everything you attempted right. With 1/3 negative marking a "
                    f"blind guess is worth {be} marks on average — so if you could rule out even one option on "
                    f"those, guessing would have gained you marks.")
    elif lost >= 3:
        coaching = (f"Negative marking cost you {lost} marks across {wrong} wrong answers. A pure guess breaks even "
                    f"at {be} marks, so the losses come from answers you felt sure about but weren't — "
                    f"worth reviewing those topics rather than guessing less.")
    elif attempted == total:
        coaching = ("You attempted every question. That is the right call only when you can eliminate options — "
                    f"a blind guess averages {be} marks under 1/3 negative marking.")
    else:
        coaching = (f"Balanced paper: {attempted} attempted, {blank} left blank, {lost} marks lost to negatives. "
                    "Keep skipping the ones where you cannot eliminate at least one option.")

    return ExamResultOut(
        id=s.id, total=total, attempted=attempted, correct=correct, wrong=wrong, blank=blank,
        raw_score=raw, marks_lost_to_negative=lost,
        accuracy=(correct / attempted) if attempted else 0.0,
        percentage=round(max(raw, 0) / total * 100, 1) if total else 0.0,
        points=pts, time_taken_seconds=elapsed,
        per_topic=sorted(per_topic.values(), key=lambda b: (-b["total"], b["topic"])),
        guess_break_even=be, coaching=coaching, review=review,
    )
