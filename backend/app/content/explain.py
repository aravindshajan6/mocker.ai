"""On-demand deeper explanations.

A one-line explanation tells you the answer; it does not always tell you why, or give you anything
to hold on to. "Explain more" asks the model for a short, exam-focused expansion plus a memory hook.

Two design constraints shape this:
  * It is grounded. The model is given the question, the options, the correct answer and our own
    explanation, and told to expand on them. Ungrounded generation on this material hallucinates
    dates and names badly (a test run invented 4 of 5 "exam facts"), so it is never asked to recall
    anything on its own.
  * It is cached permanently on the question. Generation is the expensive part and the answer never
    changes, so the first learner to ask pays for it and everyone after reads it for free. Without
    this the free tier is exhausted by a handful of active users.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Question
from ..services.quiz import today
from . import llm

log = logging.getLogger("explain")

SYSTEM_PROMPT = """You help candidates preparing for Indian state public service exams (Kerala PSC, SSC, UPSC
prelims) understand a question they have just answered.

You are given the question, its options, which option is correct, and a short explanation. Expand on
THAT material only. Never introduce a date, a name, a statistic or an event that is not already
implied by what you were given — if you are unsure of a specific fact, describe the idea instead.

Produce:
  "why": one or two sentences on why the correct option is correct, at the depth an examiner expects.
  "remember": the single most exam-relevant takeaway, stated as a crisp fact worth memorising.
  "hook": a short memory aid — a mnemonic, a link to something familiar, or a vivid association.
          Keep it under 20 words and make it genuinely memorable, not a restatement.

Do not discuss the wrong options individually; claims about them are where mistakes creep in.
Write plain, warm English. No markdown, no bullet characters.

Respond with ONLY a JSON object of this shape: {"why":"...","remember":"...","hook":"..."}"""

# Explanations are cached forever, so the cost is bounded by unique questions rather than users.
# This budget is a backstop against a runaway loop, and resets when the process restarts.
_budget = {"day": None, "used": 0}


def _take_budget() -> bool:
    d = today()
    if _budget["day"] != d:
        _budget.update(day=d, used=0)
    if _budget["used"] >= settings.explain_daily_budget:
        return False
    _budget["used"] += 1
    return True


def budget_left() -> int:
    if _budget["day"] != today():
        return settings.explain_daily_budget
    return max(0, settings.explain_daily_budget - _budget["used"])


class ExplainUnavailable(RuntimeError):
    pass


async def explain(db: AsyncSession, q: Question) -> str:
    """Return a cached deeper explanation, generating it once if needed."""
    if q.explanation_long:
        return q.explanation_long

    from ..services import llm_keys
    if not await llm_keys.configs(db, settings.explain_model):
        raise ExplainUnavailable("Deeper explanations need an LLM key to be configured.")
    if not _take_budget():
        raise ExplainUnavailable("Today's explanation budget is used up — please try again tomorrow.")

    opts = "\n".join(f"  ({chr(65 + i)}) {o}" for i, o in enumerate(q.options))
    user = (f"Question: {q.text}\nOptions:\n{opts}\n"
            f"Correct answer: ({chr(65 + q.correct_index)}) {q.options[q.correct_index]}\n"
            f"Existing explanation: {q.explanation or '(none)'}")
    try:
        # Walks the stored keys in priority order; a rate-limited or rejected key steps aside and
        # the next one is tried, so a spent free tier does not take the feature down.
        data, _cfg = await llm_keys.complete_json_failover(
            db, SYSTEM_PROMPT, user, max_tokens=900, model_override=settings.explain_model)
    except llm.LLMError as e:
        log.warning("explain failed for question %s: %s", q.id, e)
        raise ExplainUnavailable("Could not reach the explanation service just now.") from e

    why = str(data.get("why") or "").strip()
    remember = str(data.get("remember") or "").strip()
    hook = str(data.get("hook") or "").strip()
    if not why:
        raise ExplainUnavailable("The explanation came back empty — please try again.")
    parts = [why]
    if remember:
        parts.append(f"Worth remembering: {remember}")
    if hook:
        parts.append(f"Memory hook: {hook}")
    text = "\n\n".join(parts)[:2000]

    q.explanation_long = text
    await db.commit()
    return text
