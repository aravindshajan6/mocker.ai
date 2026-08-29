from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import Attempt, Question, QuizSession, ReviewCard, Topic, User, UserStats, utcnow
from ..content.explain import ExplainUnavailable, explain
from ..schemas import (ActiveSessionOut, AnswerIn, AnswerOut, AttemptState, DailyOut, ExplainOut, FinishOut,
                       QuestionOut, SessionOut, StartQuizIn)
from ..services import scoring, srs
from ..services.quiz import (current_affairs_ids, due_question_ids, effective_streak, personal_daily_ids,
                             pick_questions, today, touch_streak, weak_topic_ids)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


async def _get_stats(db: AsyncSession, user_id: str) -> UserStats:
    stats = await db.get(UserStats, user_id)
    if not stats:
        stats = UserStats(user_id=user_id)
        db.add(stats)
        await db.flush()
    return stats


async def _session_out(db: AsyncSession, s: QuizSession) -> SessionOut:
    qs = (await db.execute(select(Question, Topic).join(Topic, Topic.id == Question.topic_id)
                           .where(Question.id.in_(s.question_ids)))).all()
    by_id = {q.id: (q, t) for q, t in qs}
    questions = []
    for qid in s.question_ids:
        if qid in by_id:
            q, t = by_id[qid]
            questions.append(QuestionOut(id=q.id, text=q.text, options=q.options, difficulty=q.difficulty,
                                         topic=t.name, topic_icon=t.icon, published_at=q.published_at,
                                         source_ref=q.source_ref))
    attempts = (await db.execute(select(Attempt).where(Attempt.session_id == s.id).order_by(Attempt.id))).scalars().all()
    topic_name = None
    if s.topic_id:
        topic_name = (await db.get(Topic, s.topic_id)).name
    return SessionOut(
        id=s.id, mode=s.mode, topic=topic_name, questions=questions,
        attempts=[AttemptState(question_id=a.question_id, selected_index=a.selected_index, is_correct=a.is_correct,
                               correct_index=by_id[a.question_id][0].correct_index if a.question_id in by_id else 0,
                               explanation=by_id[a.question_id][0].explanation if a.question_id in by_id else "",
                               points=a.points,
                               source_url=by_id[a.question_id][0].source_url if a.question_id in by_id else None,
                               source_ref=by_id[a.question_id][0].source_ref if a.question_id in by_id else None)
                  for a in attempts],
        score=s.score, correct=s.correct, finished=s.finished_at is not None,
    )


@router.get("/daily", response_model=DailyOut)
async def daily_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    day = today()
    ids = await personal_daily_ids(db, user.id, day)
    s = (await db.execute(select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.daily_date == day,
                                                    QuizSession.mode == "daily")
                          .order_by(QuizSession.started_at.desc()))).scalars().first()
    return DailyOut(day=day, size=len(ids), done=bool(s and s.finished_at), session_id=s.id if s else None,
                    score=s.score if s and s.finished_at else None, correct=s.correct if s and s.finished_at else None)


@router.post("/question/{question_id}/explain", response_model=ExplainOut)
async def explain_question(question_id: int, user: User = Depends(current_user),
                           db: AsyncSession = Depends(get_db)):
    """A deeper explanation with a memory hook. Only available once the user has answered it."""
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    seen = (await db.execute(select(Attempt.id).where(Attempt.user_id == user.id,
                                                       Attempt.question_id == question_id).limit(1))).scalar()
    if not seen:
        raise HTTPException(403, "Answer the question first")
    cached = bool(q.explanation_long)
    try:
        text = await explain(db, q)
    except ExplainUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return ExplainOut(question_id=question_id, explanation=text, cached=cached)


@router.get("/active", response_model=list[ActiveSessionOut])
async def active_sessions(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Unfinished quizzes the user can resume (most recent first)."""
    rows = (await db.execute(
        select(QuizSession, Topic).outerjoin(Topic, Topic.id == QuizSession.topic_id)
        .where(QuizSession.user_id == user.id, QuizSession.finished_at.is_(None))
        .options(selectinload(QuizSession.attempts))
        .order_by(QuizSession.started_at.desc()).limit(5)
    )).all()
    return [ActiveSessionOut(id=s.id, mode=s.mode, topic=t.name if t else None, topic_icon=t.icon if t else None,
                             answered=len(s.attempts), total=len(s.question_ids)) for s, t in rows]


@router.post("/{session_id}/abandon")
async def abandon(session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Delete an unfinished quiz (used when the user exits before answering anything)."""
    s = await db.get(QuizSession, session_id)
    if not s or s.user_id != user.id or s.mode == "exam":
        raise HTTPException(404, "Quiz not found")
    if s.finished_at:
        raise HTTPException(409, "Finished quizzes cannot be removed")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.post("/start", response_model=SessionOut)
async def start_quiz(data: StartQuizIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    topic_id = None
    daily_date: date | None = None
    if data.mode == "daily":
        daily_date = today()
        existing = (await db.execute(select(QuizSession).where(QuizSession.user_id == user.id, QuizSession.mode == "daily",
                                                                QuizSession.daily_date == daily_date))).scalars().first()
        if existing:
            return await _session_out(db, existing)  # resume (or view finished) — one daily per day
        ids = await personal_daily_ids(db, user.id, daily_date)
    elif data.mode == "weak":
        ids = await weak_topic_ids(db, user.id, data.count or settings.topic_quiz_size)
    elif data.mode == "review":
        ids = await due_question_ids(db, user.id, data.count or 15)
        if not ids:
            raise HTTPException(409, "Nothing is due for review right now")
    elif data.mode == "current-affairs":
        day = data.day or today()
        existing = (await db.execute(select(QuizSession).where(QuizSession.user_id == user.id,
                                                                QuizSession.mode == "current-affairs",
                                                                QuizSession.daily_date == day))).scalars().first()
        if existing:
            return await _session_out(db, existing)  # one session per day per user; resumable
        ids = await current_affairs_ids(db, day)
        if not ids:
            raise HTTPException(409, "No current-affairs questions for that day yet")
        daily_date = day
    else:
        count = data.count or settings.topic_quiz_size
        if data.mode == "topic":
            if not data.topic:
                raise HTTPException(422, "topic is required")
            t = (await db.execute(select(Topic).where(Topic.slug == data.topic))).scalar_one_or_none()
            if not t:
                raise HTTPException(404, "Unknown topic")
            topic_id = t.id
        ids = await pick_questions(db, user.id, count, topic_id=topic_id, exclude_current_affairs=False)
    if not ids:
        raise HTTPException(409, "No questions available yet for this selection")
    s = QuizSession(user_id=user.id, mode=data.mode, topic_id=topic_id, daily_date=daily_date, question_ids=ids)
    db.add(s)
    await db.commit()
    return await _session_out(db, s)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    s = await db.get(QuizSession, session_id)
    if not s or s.user_id != user.id or s.mode == "exam":
        # Exams are served only by the exam router: this response carries correct_index for every
        # attempt, which would hand a candidate the answer key mid-paper.
        raise HTTPException(404, "Quiz not found")
    return await _session_out(db, s)


@router.post("/{session_id}/answer", response_model=AnswerOut)
async def answer(session_id: str, data: AnswerIn, user: User = Depends(current_user),
                 db: AsyncSession = Depends(get_db)):
    s = await db.get(QuizSession, session_id, options=[selectinload(QuizSession.attempts)])
    if not s or s.user_id != user.id or s.mode == "exam":
        raise HTTPException(404, "Quiz not found")   # exam answers go through /api/exam/*
    if s.finished_at:
        raise HTTPException(409, "This quiz is already finished")
    if data.question_id not in s.question_ids:
        raise HTTPException(400, "Question is not part of this quiz")
    q = await db.get(Question, data.question_id)
    if any(a.question_id == q.id for a in s.attempts):
        raise HTTPException(409, "Already answered")
    if data.selected_index >= len(q.options):
        raise HTTPException(400, "Invalid option")

    is_correct = data.selected_index == q.correct_index
    # combo = consecutive correct answers in this session, in question order
    answered_map = {a.question_id: a for a in s.attempts}
    combo = 0
    for qid in s.question_ids:
        if qid == q.id:
            break
        a = answered_map.get(qid)
        if a and a.is_correct:
            combo += 1
        elif a:
            combo = 0
    combo = combo + 1 if is_correct else 0
    pts = scoring.points_for(is_correct, q.difficulty, combo)

    db.add(Attempt(session_id=s.id, user_id=user.id, question_id=q.id, selected_index=data.selected_index,
                   is_correct=is_correct, points=pts))
    try:
        await db.flush()          # surfaces the unique constraint before anything else is written
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Already answered") from None
    s.score += pts
    s.correct += 1 if is_correct else 0

    await _schedule_review(db, user.id, q.id, is_correct, data.elapsed_ms)

    stats = await _get_stats(db, user.id)
    stats.total_points += pts
    stats.questions_answered += 1
    stats.correct_answers += 1 if is_correct else 0
    day = today()
    change = touch_streak(stats, day)
    await db.commit()

    return AnswerOut(
        is_correct=is_correct, correct_index=q.correct_index, explanation=q.explanation, source_url=q.source_url,
        source_ref=q.source_ref,
        points=pts, combo=combo,
        score=s.score, correct=s.correct, answered=len(s.attempts) + 1, total=len(s.question_ids),
        streak=effective_streak(stats, day), streak_extended=change.extended,
        streak_repaired=change.repaired, repairs_left=change.repairs_left,
        milestone=change.milestone, milestone_title=_milestone_copy(change.milestone)[0],
        milestone_body=_milestone_copy(change.milestone)[1],
    )


@router.post("/{session_id}/finish", response_model=FinishOut)
async def finish(session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    s = await db.get(QuizSession, session_id, options=[selectinload(QuizSession.attempts)])
    if not s or s.user_id != user.id or s.mode == "exam":
        raise HTTPException(404, "Quiz not found")   # exams are graded by /api/exam/{id}/submit
    stats = await _get_stats(db, user.id)
    total = len(s.question_ids)
    new_badges: list[str] = []
    if s.finished_at is None and len(s.attempts) < total:
        raise HTTPException(409, "Answer all questions first")
    # Exactly one concurrent request may claim the finish; the losers report already_finished.
    claimed = (await db.execute(
        update(QuizSession).where(QuizSession.id == s.id, QuizSession.finished_at.is_(None))
        .values(finished_at=utcnow()).returning(QuizSession.id)
    )).scalar_one_or_none() is not None
    already = not claimed
    if claimed:
        before = set(await _badges(db, user.id, stats))
        bonus = 0
        if s.mode == "daily":
            bonus += settings.daily_bonus
        if s.correct == total and total >= 5:
            bonus += 20  # perfect round
        s.bonus = bonus
        s.score += bonus
        stats.total_points += bonus
        stats.quizzes_completed += 1
        await db.commit()
        await db.refresh(s)
        after = await _badges(db, user.id, stats)
        new_badges = [b for b in after if b not in before]
    level, title, _, to_next = scoring.level_for(stats.total_points)
    return FinishOut(
        score=s.score, bonus=s.bonus, correct=s.correct, total=total,
        accuracy=(s.correct / total) if total else 0.0, total_points=stats.total_points, level=level,
        level_title=title, points_to_next_level=to_next, streak=effective_streak(stats, today()),
        already_finished=already, new_badges=new_badges,
    )


def _milestone_copy(milestone: int | None) -> tuple[str | None, str | None]:
    if not milestone:
        return None, None
    title, body = scoring.MILESTONE_COPY.get(milestone, ("Milestone reached", ""))
    return title, body


async def _schedule_review(db: AsyncSession, user_id: str, question_id: int, is_correct: bool,
                           elapsed_ms: int | None) -> None:
    """Every answer feeds the spaced-repetition schedule, so reviews build up from normal practice."""
    card = await db.get(ReviewCard, (user_id, question_id))
    state, due, lapsed = srs.review(card.state if card else None, is_correct, elapsed_ms)
    if card:
        card.state, card.due_at, card.reps = state, due, card.reps + 1
        card.lapses += 1 if lapsed else 0
        card.last_reviewed_at = utcnow()
    else:
        db.add(ReviewCard(user_id=user_id, question_id=question_id, state=state, due_at=due,
                          reps=1, lapses=0, last_reviewed_at=utcnow()))


async def _badges(db: AsyncSession, user_id: str, stats: UserStats) -> list[str]:
    from sqlalchemy import func
    perfect = (await db.execute(
        select(func.count()).select_from(QuizSession).where(
            QuizSession.user_id == user_id, QuizSession.finished_at.is_not(None),
            QuizSession.correct == func.json_array_length(QuizSession.question_ids),
        )
    )).scalar_one()
    return scoring.badges_for(
        total_points=stats.total_points, streak=stats.current_streak, longest_streak=stats.longest_streak,
        answered=stats.questions_answered, correct=stats.correct_answers, quizzes=stats.quizzes_completed,
        perfect_quizzes=perfect,
    )
