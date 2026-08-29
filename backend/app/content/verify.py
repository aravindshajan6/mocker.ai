"""Automated audit of the answer keys on bulk-imported questions.

Hand-authored questions and real exam papers carry their own authority. The MILU import does not:
a sample review found roughly one in twenty had a wrong or ambiguous answer key. Shipping those to
someone revising for an exam actively teaches them the wrong fact, which is worse than not having
the question at all.

So every night we ask an LLM to audit a slice of the imported bank. It only ever *removes* trust:
a high-confidence "wrong answer" deactivates the question, a middling verdict tags it for a human
to look at, and anything it judges fine is simply marked as checked so we do not pay to check it
again. It never rewrites a question or changes an answer key on its own.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Question, utcnow
from . import llm

log = logging.getLogger("verify")

AUDITED_SOURCES = ("milu",)  # seed / pyq / news questions are trusted by provenance

SYSTEM_PROMPT = """You are auditing multiple-choice questions from an Indian general-knowledge exam bank.
For each question you are given the options and which one the bank marks as correct.

Judge ONLY whether the marked answer is right. Do not rewrite the question, do not suggest new options.

Return for each item a verdict:
  "ok"           - the marked answer is correct.
  "wrong_answer" - the marked answer is factually wrong AND a different listed option is clearly correct.
  "ambiguous"    - more than one option could be defended, no option is correct, the question is
                   unanswerable as written, or it depends on a date/context that is not given.

Also return a confidence between 0 and 1 for your verdict, and for "wrong_answer" the index of the
option you believe is correct. Be conservative: if you are not sure the bank is wrong, say "ok".
A false accusation removes a valid question, so only flag what you can actually justify.

Respond with ONLY a JSON object:
{"results":[{"index":0,"verdict":"ok","confidence":0.95,"correct_index":null,"note":""}]}
Include exactly one result per question, in the order given. Keep notes under 160 characters."""


async def pending(db: AsyncSession, limit: int) -> list[Question]:
    """Imported questions that have never been audited, oldest first."""
    return list((await db.execute(
        select(Question)
        .where(Question.source.in_(AUDITED_SOURCES), Question.verified_at.is_(None),
               Question.is_active.is_(True))
        .order_by(Question.id).limit(limit)
    )).scalars().all())


def _audit_batch(batch: list[Question], cfg: llm.LLMConfig) -> list[dict]:
    lines = []
    for i, q in enumerate(batch):
        opts = "; ".join(f"[{j}] {o}" for j, o in enumerate(q.options))
        lines.append(f"{i}. Q: {q.text}\n   Options: {opts}\n   Bank says correct: [{q.correct_index}] {q.options[q.correct_index]}")
    data = llm.complete_json(SYSTEM_PROMPT, "\n\n".join(lines), max_tokens=2500, cfg=cfg)
    results = data.get("results") if isinstance(data, dict) else None
    return results if isinstance(results, list) else []


async def run_audit(db: AsyncSession, limit: int | None = None) -> dict:
    """Audit up to `limit` unchecked questions. Returns a summary dict."""
    cfg = llm.current_config()
    if settings.verify_model:
        cfg = llm.LLMConfig(cfg.provider, cfg.api_key, settings.verify_model, cfg.base_url)
    summary = {"checked": 0, "ok": 0, "wrong": 0, "ambiguous": 0, "deactivated": 0, "flagged": 0,
               "model": cfg.model, "errors": 0}
    if not cfg.available:
        summary["errors"] = 1
        summary["message"] = "no LLM key configured"
        return summary

    todo = await pending(db, limit or settings.verify_per_night)
    if not todo:
        summary["message"] = "nothing left to audit"
        return summary

    size = settings.verify_batch_size
    for start in range(0, len(todo), size):
        batch = todo[start:start + size]
        try:
            results = _audit_batch(batch, cfg)
        except llm.LLMError as e:
            msg = str(e)
            log.warning("audit batch at %d failed: %s", start, msg)
            summary["errors"] += 1
            if "HTTP 401" in msg or "HTTP 403" in msg or "no API key" in msg:
                break
            if "rate limited" in msg:
                time.sleep(65)
            continue

        for r in results:
            idx = r.get("index")
            if not isinstance(idx, int) or not 0 <= idx < len(batch):
                continue
            q = batch[idx]
            verdict = r.get("verdict") if r.get("verdict") in ("ok", "wrong_answer", "ambiguous") else "ok"
            conf = float(r.get("confidence") or 0)
            q.verified_at = utcnow()
            q.verdict = verdict
            q.verdict_confidence = conf
            q.verdict_note = (r.get("note") or "")[:300]
            summary["checked"] += 1
            if verdict == "ok":
                summary["ok"] += 1
                continue
            summary["wrong" if verdict == "wrong_answer" else "ambiguous"] += 1
            if conf >= settings.verify_autodisable_confidence:
                # Confidently bad: stop serving it. Nothing is deleted, so it can be restored.
                q.is_active = False
                summary["deactivated"] += 1
            else:
                summary["flagged"] += 1
        await db.commit()
        time.sleep(2)  # stay inside the free tier's per-minute token budget

    log.info("audit: %s", summary)
    return summary


async def stats(db: AsyncSession) -> dict:
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(Question)
                              .where(Question.source.in_(AUDITED_SOURCES)))).scalar_one()
    checked = (await db.execute(select(func.count()).select_from(Question)
                                .where(Question.source.in_(AUDITED_SOURCES),
                                       Question.verified_at.is_not(None)))).scalar_one()
    rows = (await db.execute(select(Question.verdict, func.count()).where(Question.verdict.is_not(None))
                             .group_by(Question.verdict))).all()
    disabled = (await db.execute(select(func.count()).select_from(Question)
                                 .where(Question.is_active.is_(False),
                                        Question.verdict.is_not(None)))).scalar_one()
    flagged = (await db.execute(select(func.count()).select_from(Question)
                                .where(Question.is_active.is_(True),
                                       or_(Question.verdict == "wrong_answer",
                                           Question.verdict == "ambiguous")))).scalar_one()
    return {"audited_pool": total, "checked": checked, "remaining": total - checked,
            "by_verdict": {v: c for v, c in rows}, "deactivated": disabled, "flagged_for_review": flagged}
