"""Administrator surface.

Everything that changes content, accounts or provider configuration lives here behind
`current_admin`. Ordinary learners can read questions and record their own answers; they cannot add
or edit questions, trigger content jobs, see other accounts, or touch API keys.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_admin, hash_password
from ..config import settings
from ..content import llm
from ..content.current_affairs import run_daily
from ..content.verify import run_audit, stats as audit_stats
from ..db import SessionLocal, get_db
from ..models import (Attempt, ContentRun, LLMCredential, Question, QuizSession, Topic, User, UserPrefs,
                      UserStats, utcnow)
from ..schemas import (AdminOverview, AdminQuestionIn, AdminQuestionOut, AdminQuestionsOut, AdminUserRow,
                       CredentialIn, CredentialOut, CredentialPatch, CredentialTestOut, CreateUserIn,
                       JobOut, ResetPasswordIn)
from ..seed import fingerprint
from ..services import llm_keys

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


# --------------------------------------------------------------------- overview ----
@router.get("/overview", response_model=AdminOverview)
async def overview(db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    admins = (await db.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))).scalar_one()
    active = (await db.execute(select(func.count()).select_from(Question).where(Question.is_active.is_(True)))).scalar_one()
    by_source = dict((await db.execute(
        select(Question.source, func.count()).where(Question.is_active.is_(True)).group_by(Question.source)
    )).all())
    by_topic = [
        {"slug": s, "name": n, "icon": i, "count": c}
        for s, n, i, c in (await db.execute(
            select(Topic.slug, Topic.name, Topic.icon, func.count(Question.id))
            .join(Question, (Question.topic_id == Topic.id) & (Question.is_active.is_(True)))
            .group_by(Topic.slug, Topic.name, Topic.icon, Topic.sort_order).order_by(Topic.sort_order)
        )).all()
    ]
    attempts = (await db.execute(select(func.count()).select_from(Attempt))).scalar_one()
    finished = (await db.execute(select(func.count()).select_from(QuizSession)
                                 .where(QuizSession.finished_at.is_not(None)))).scalar_one()
    last = (await db.execute(select(ContentRun).where(ContentRun.status != "skipped")
                             .order_by(ContentRun.started_at.desc()).limit(1))).scalars().first()
    from ..routers.current_affairs import _run_out
    keys = len(await llm_keys.usable(db))
    env = llm.current_config()
    return AdminOverview(
        users=users, admins=admins, questions_active=active, questions_by_source=by_source,
        questions_by_topic=by_topic, attempts=attempts, sessions_finished=finished,
        last_content_run=_run_out(last), audit=await audit_stats(db),
        llm_keys_active=keys, llm_provider=env.provider, llm_available=keys > 0 or env.available,
    )


# ------------------------------------------------------------------ content jobs ----
@router.post("/content/current-affairs/run", response_model=JobOut)
async def run_current_affairs(background: BackgroundTasks, force: bool = False, wait: bool = False,
                              db: AsyncSession = Depends(get_db)):
    """Fetch today's news and generate questions from it."""
    if wait:
        summary = await run_daily(db, force=force)
        return JobOut(started=True, detail="Finished", result=summary)

    async def _bg():
        async with SessionLocal() as s:
            await run_daily(s, force=force)

    background.add_task(_bg)
    return JobOut(started=True, detail="Running in the background — refresh in a minute or two.")


@router.post("/content/audit/run", response_model=JobOut)
async def run_verification(background: BackgroundTasks, limit: int = 50, wait: bool = False,
                           db: AsyncSession = Depends(get_db)):
    """Audit imported answer keys with the LLM."""
    if wait:
        return JobOut(started=True, detail="Finished", result=await run_audit(db, limit=limit))

    async def _bg():
        async with SessionLocal() as s:
            await run_audit(s, limit=limit)

    background.add_task(_bg)
    return JobOut(started=True, detail=f"Auditing {limit} questions in the background.")


# --------------------------------------------------------------------- questions ----
@router.get("/questions", response_model=AdminQuestionsOut)
async def list_questions(q: str | None = None, topic: str | None = None, source: str | None = None,
                         only: str = "all", limit: int = 25, offset: int = 0,
                         db: AsyncSession = Depends(get_db)):
    limit, offset = max(1, min(limit, 100)), max(0, offset)
    base = select(Question, Topic).join(Topic, Topic.id == Question.topic_id)
    if q:
        base = base.where(Question.text.ilike(f"%{q}%"))
    if topic:
        base = base.where(Topic.slug == topic)
    if source:
        base = base.where(Question.source == source)
    if only == "active":
        base = base.where(Question.is_active.is_(True))
    elif only == "inactive":
        base = base.where(Question.is_active.is_(False))
    elif only == "flagged":
        base = base.where(Question.verdict.in_(("wrong_answer", "ambiguous")))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(Question.id.desc()).limit(limit).offset(offset))).all()
    counts = dict((await db.execute(
        select(Attempt.question_id, func.count()).where(
            Attempt.question_id.in_([r[0].id for r in rows] or [0])
        ).group_by(Attempt.question_id)
    )).all())
    return AdminQuestionsOut(
        questions=[_question_out(qq, t, counts.get(qq.id, 0)) for qq, t in rows],
        total=total, offset=offset, limit=limit,
    )


def _question_out(q: Question, t: Topic, answered: int) -> AdminQuestionOut:
    return AdminQuestionOut(
        id=q.id, text=q.text, options=q.options, correct_index=q.correct_index,
        explanation=q.explanation, difficulty=q.difficulty, topic=t.name, topic_slug=t.slug,
        source=q.source, source_ref=q.source_ref, is_active=q.is_active, verdict=q.verdict,
        verdict_note=q.verdict_note, times_answered=answered,
    )


@router.post("/questions", response_model=AdminQuestionOut)
async def create_question(data: AdminQuestionIn, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Topic).where(Topic.slug == data.topic))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Unknown topic")
    opts = [o.strip() for o in data.options]
    if len(set(o.lower() for o in opts)) != 4 or any(not o for o in opts):
        raise HTTPException(422, "Give four different, non-empty options")
    fp = fingerprint(data.question)
    if (await db.execute(select(Question.id).where(Question.fingerprint == fp))).scalar():
        raise HTTPException(409, "That question is already in the bank")
    q = Question(topic_id=t.id, text=data.question.strip(), options=opts, correct_index=data.answer,
                 explanation=data.explanation.strip(), difficulty=data.difficulty,
                 tags=data.tags, source="admin", fingerprint=fp, source_ref="Added by an administrator")
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _question_out(q, t, 0)


@router.patch("/questions/{question_id}", response_model=AdminQuestionOut)
async def update_question(question_id: int, data: AdminQuestionIn, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    t = (await db.execute(select(Topic).where(Topic.slug == data.topic))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Unknown topic")
    opts = [o.strip() for o in data.options]
    if len(set(o.lower() for o in opts)) != 4 or any(not o for o in opts):
        raise HTTPException(422, "Give four different, non-empty options")
    q.topic_id, q.text, q.options = t.id, data.question.strip(), opts
    q.correct_index, q.explanation, q.difficulty = data.answer, data.explanation.strip(), data.difficulty
    q.tags = data.tags
    q.fingerprint = fingerprint(data.question)
    # An edited question has not been audited in its new form.
    q.verdict = q.verdict_note = q.verified_at = None
    await db.commit()
    return _question_out(q, t, 0)


@router.post("/questions/{question_id}/toggle", response_model=AdminQuestionOut)
async def toggle_question(question_id: int, db: AsyncSession = Depends(get_db)):
    """Retire a question from circulation, or bring it back. Nothing is ever deleted: attempts
    reference it, and a removed question still needs to render in someone's review history."""
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    q.is_active = not q.is_active
    await db.commit()
    t = await db.get(Topic, q.topic_id)
    return _question_out(q, t, 0)


# ------------------------------------------------------------------------- users ----
@router.get("/users", response_model=list[AdminUserRow])
async def list_users(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(User, func.count(Attempt.id), func.max(UserStats.last_active_date))
        .outerjoin(Attempt, Attempt.user_id == User.id)
        .outerjoin(UserStats, UserStats.user_id == User.id)
        .group_by(User.id).order_by(User.created_at)
    )).all()
    return [AdminUserRow(id=u.id, name=u.name, email=u.email, is_admin=u.is_admin,
                         created_at=u.created_at, answered=n, last_active=last)
            for u, n, last in rows]


@router.post("/users", response_model=AdminUserRow)
async def create_user(data: CreateUserIn, db: AsyncSession = Depends(get_db)):
    """Sign-up is closed, so this is how a learner gets an account."""
    email = data.email.lower()
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "An account with that email already exists")
    u = User(email=email, name=data.name.strip(), password_hash=hash_password(data.password),
             is_admin=data.is_admin)
    u.stats = UserStats()
    db.add(u)
    await db.flush()
    db.add(UserPrefs(user_id=u.id))
    await db.commit()
    return AdminUserRow(id=u.id, name=u.name, email=u.email, is_admin=u.is_admin,
                        created_at=u.created_at, answered=0, last_active=None)


@router.post("/users/{user_id}/password")
async def reset_password(user_id: str, data: ResetPasswordIn, db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Account not found")
    u.password_hash = hash_password(data.password)
    await db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(409, "You cannot delete the account you are signed in with")
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Account not found")
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return {"ok": True}


# ------------------------------------------------------------------- LLM keys ----
def _cred_out(c: LLMCredential) -> CredentialOut:
    cooling = bool(c.cooldown_until and c.cooldown_until > utcnow())
    return CredentialOut(
        id=c.id, label=c.label, provider=c.provider, api_key_masked=llm_keys.mask(c.api_key),
        model=c.model, base_url=c.base_url, priority=c.priority, is_active=c.is_active,
        cooling_down=cooling, cooldown_until=c.cooldown_until, last_used_at=c.last_used_at,
        last_error=c.last_error, created_at=c.created_at,
    )


@router.get("/llm/providers")
async def llm_providers():
    """What can be plugged in, and what each one defaults to."""
    return {
        "providers": [
            {"id": p, "base_url": base, "default_model": model,
             "free_tier": p in ("groq", "gemini", "openrouter", "ollama")}
            for p, (base, model) in llm.PROVIDERS.items()
        ],
        "env_provider": llm.current_config().provider,
        "env_key_present": llm.current_config().available,
    }


@router.get("/llm/keys", response_model=list[CredentialOut])
async def list_keys(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(LLMCredential).order_by(LLMCredential.priority, LLMCredential.id))).scalars().all()
    return [_cred_out(c) for c in rows]


@router.post("/llm/keys", response_model=CredentialOut)
async def add_key(data: CredentialIn, db: AsyncSession = Depends(get_db)):
    if data.provider not in llm.PROVIDERS:
        raise HTTPException(422, f"Unknown provider. Choose one of: {', '.join(llm.PROVIDERS)}")
    if (await db.execute(select(LLMCredential).where(LLMCredential.api_key == data.api_key))).scalar_one_or_none():
        raise HTTPException(409, "That key is already stored")
    c = LLMCredential(label=data.label.strip(), provider=data.provider, api_key=data.api_key.strip(),
                      model=data.model.strip(), base_url=data.base_url.strip(), priority=data.priority)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return _cred_out(c)


@router.patch("/llm/keys/{key_id}", response_model=CredentialOut)
async def update_key(key_id: int, data: CredentialPatch, db: AsyncSession = Depends(get_db)):
    c = await db.get(LLMCredential, key_id)
    if not c:
        raise HTTPException(404, "Key not found")
    if data.label is not None:
        c.label = data.label.strip()
    if data.model is not None:
        c.model = data.model.strip()
    if data.priority is not None:
        c.priority = data.priority
    if data.is_active is not None:
        c.is_active = data.is_active
    if data.clear_cooldown:
        c.cooldown_until = None
        c.last_error = None
    await db.commit()
    return _cred_out(c)


@router.delete("/llm/keys/{key_id}")
async def delete_key(key_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(LLMCredential, key_id)
    if not c:
        raise HTTPException(404, "Key not found")
    await db.delete(c)
    await db.commit()
    return {"ok": True}


@router.post("/llm/keys/{key_id}/test", response_model=CredentialTestOut)
async def test_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Make a real (tiny) call so an admin knows a key works before relying on it."""
    c = await db.get(LLMCredential, key_id)
    if not c:
        raise HTTPException(404, "Key not found")
    cfg = llm_keys.to_config(c)
    started = time.monotonic()
    try:
        data = await asyncio.to_thread(
            llm.complete_json,
            'Reply with JSON only.',
            'Return exactly {"ok": true}.',
            max_tokens=200, cfg=cfg,
        )
    except llm.LLMError as e:
        await llm_keys.record_failure(db, cfg, str(e))
        return CredentialTestOut(ok=False, detail=str(e)[:300], model=cfg.model, latency_ms=None)
    await llm_keys.record_success(db, cfg)
    return CredentialTestOut(ok=bool(data), detail="Working", model=cfg.model,
                             latency_ms=int((time.monotonic() - started) * 1000))
