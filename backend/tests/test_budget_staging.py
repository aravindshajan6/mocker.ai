"""Token budgeting and the phased classification of staged questions."""
import pytest

from app.content import staging
from app.models import LLMUsage, StagedQuestion
from app.services import budget
from app.services.quiz import today


def cfg(provider="groq", model="qwen/qwen3.8-27b"):
    from app.content.llm import LLMConfig
    return LLMConfig(provider=provider, api_key="k" * 20, model=model, base_url="https://x")


# --- budget accounting -------------------------------------------------------

def test_free_tier_limits_are_known_per_model():
    assert budget.limit_for("groq", "qwen/qwen3.8-27b") == 2_000_000
    assert budget.limit_for("groq", "openai/gpt-oss-120b") == 200_000
    assert budget.limit_for("groq", "something-new") == 200_000, "unknown models fall back"
    assert budget.limit_for("ollama", "anything") == 0, "local models are not capped"


def test_a_batch_job_may_not_spend_the_whole_allowance():
    """The reserve is what keeps 'Explain this more' working after a nightly batch."""
    assert 0 < budget.BATCH_SHARE < 1


async def test_usage_is_recorded_and_accumulates(db_session):
    from sqlalchemy import delete
    model = "test/accounting-model"
    await db_session.execute(delete(LLMUsage).where(LLMUsage.model == model))
    await db_session.commit()

    c = cfg(model=model)
    await budget.record(db_session, c, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    await budget.record(db_session, c, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    b = await budget.status(db_session, c.provider, c.model)
    assert b.used == 165 and b.requests == 2

    await db_session.execute(delete(LLMUsage).where(LLMUsage.model == model))
    await db_session.commit()


async def test_spending_is_refused_once_the_batch_share_is_gone(db_session):
    from sqlalchemy import delete
    model = "test/exhausted-model"
    await db_session.execute(delete(LLMUsage).where(LLMUsage.model == model))
    db_session.add(LLMUsage(day=today(), provider="groq", model=model, requests=1,
                            prompt_tokens=0, completion_tokens=0, total_tokens=199_000))
    await db_session.commit()

    ok, why = await budget.can_spend(db_session, cfg(model=model), 5_000)
    assert ok is False and "used today" in why

    await db_session.execute(delete(LLMUsage).where(LLMUsage.model == model))
    await db_session.commit()


async def test_an_uncapped_provider_always_has_room(db_session):
    ok, _ = await budget.can_spend(db_session, cfg(provider="ollama", model="qwen2.5:7b"), 10**9)
    assert ok is True


# --- the per-minute pacer ----------------------------------------------------

async def test_pacer_allows_spending_inside_the_window():
    p = budget.MinutePacer("groq")
    assert await p.wait_for(1000) == 0.0
    p.record(1000)
    assert await p.wait_for(1000) == 0.0, "well inside the minute limit"


async def test_pacer_knows_the_per_minute_ceiling():
    p = budget.MinutePacer("groq")
    assert 0 < p.limit <= budget.MINUTE_TOKEN_LIMITS["groq"], "headroom keeps us under the real cap"


async def test_pacer_does_not_throttle_uncapped_providers():
    p = budget.MinutePacer("ollama")
    assert p.limit == 0
    assert await p.wait_for(10**9) == 0.0


# --- classification ----------------------------------------------------------

def test_the_prompt_names_every_valid_topic_and_the_drop_label():
    for slug in staging.TOPIC_SLUGS:
        assert slug in staging.SYSTEM_PROMPT
    assert staging.DROP in staging.SYSTEM_PROMPT
    p = staging.SYSTEM_PROMPT.lower()
    # the categories that leaked into the bank on the first import
    assert "pedagogy" in p and "literary criticism" in p and "grammar" in p
    assert "when unsure" in p


def test_cost_estimate_is_calibrated_not_guessed():
    """An inflated estimate makes the pacer idle while quota goes unused."""
    per_batch = staging.SYSTEM_PROMPT_TOKENS + 20 * staging.TOKENS_PER_QUESTION
    assert 1_500 <= per_batch <= 3_500, f"a batch of 20 measured ~2,240 tokens, estimate is {per_batch}"


async def test_progress_reports_the_queue(db_session):
    p = await staging.progress(db_session)
    assert p.total == p.pending + p.kept + p.dropped + p.failed
    assert p.promoted <= p.kept


async def test_classification_stops_cleanly_with_no_key(db_session, monkeypatch):
    async def no_keys(*a, **k):
        return []
    monkeypatch.setattr("app.services.llm_keys.configs", no_keys)
    out = await staging.classify_once(db_session, max_questions=5)
    assert out["considered"] == 0 and "no LLM key" in out["stopped"]


async def test_kept_questions_are_promoted_into_the_bank(db_session):
    """Anything marked kept must end up answerable, or the classification was wasted."""
    from sqlalchemy import select
    from app.models import Question

    kept = (await db_session.execute(
        select(StagedQuestion).where(StagedQuestion.status == "kept").limit(20)
    )).scalars().all()
    if not kept:
        pytest.skip("nothing classified yet in this environment")
    for row in kept:
        exists = (await db_session.execute(
            select(Question.id).where(Question.fingerprint == row.fingerprint)
        )).scalar()
        assert exists, f"kept staged question {row.id} never reached the bank"


# --- admin surface -----------------------------------------------------------

def test_staging_endpoints_are_admin_only(client, user):
    assert client.get("/api/admin/staging").status_code == 403
    assert client.post("/api/admin/staging/run").status_code == 403
    assert client.post("/api/admin/staging/load").status_code == 403


def test_staging_status_reports_budget_and_schedule(client, admin):
    s = client.get("/api/admin/staging").json()
    assert s["total"] == s["pending"] + s["kept"] + s["dropped"] + s["failed"]
    assert s["model"] and 0 <= s["scheduled_hour_ist"] <= 23
    for b in s["budgets"]:
        assert b["used"] >= 0 and b["batch_remaining"] <= b["limit"]
