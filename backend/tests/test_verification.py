"""Automated answer-key audit of bulk-imported questions."""
import pytest
from sqlalchemy import select

from app.content import verify
from app.models import Question


def test_only_imported_sources_are_audited():
    # Hand-authored questions and real exam papers carry their own provenance and must not be
    # second-guessed by a model.
    assert verify.AUDITED_SOURCES == ("milu",)
    assert "seed" not in verify.AUDITED_SOURCES
    assert "pyq" not in verify.AUDITED_SOURCES


def test_the_prompt_tells_the_model_to_be_conservative():
    p = verify.SYSTEM_PROMPT.lower()
    assert "conservative" in p
    assert "do not rewrite" in p
    assert '"ok"' in p and '"wrong_answer"' in p and '"ambiguous"' in p


@pytest.mark.parametrize("verdict,confidence,should_disable", [
    ("wrong_answer", 0.99, True),
    ("wrong_answer", 0.50, False),   # uncertain: flag for a human, keep serving
    ("ambiguous", 0.90, True),
    ("ok", 0.99, False),
])
def test_autodisable_threshold_policy(verdict, confidence, should_disable):
    from app.config import settings
    disables = verdict != "ok" and confidence >= settings.verify_autodisable_confidence
    assert disables is should_disable


async def test_audit_endpoint_requires_the_admin_token(client, user):
    assert client.get("/api/admin/verification").status_code == 403
    assert client.post("/api/admin/verification/run").status_code == 403


async def test_pending_only_returns_unaudited_active_imported_questions(db_session):
    rows = await verify.pending(db_session, 5)
    for q in rows:
        assert q.source in verify.AUDITED_SOURCES
        assert q.verified_at is None
        assert q.is_active is True


async def test_audit_stats_shape(db_session):
    s = await verify.stats(db_session)
    assert {"audited_pool", "checked", "remaining", "by_verdict", "deactivated", "flagged_for_review"} <= set(s)
    assert s["audited_pool"] >= s["checked"]
    assert s["remaining"] == s["audited_pool"] - s["checked"]


async def test_deactivated_questions_are_never_served(db_session):
    """A question the auditor rejected must not reach a learner."""
    dead = (await db_session.execute(
        select(Question).where(Question.is_active.is_(False)).limit(5)
    )).scalars().all()
    for q in dead:
        assert q.is_active is False
