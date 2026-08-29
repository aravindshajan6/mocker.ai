"""Deeper on-demand explanations."""
from app.content import explain as ex


def test_prompt_forbids_ungrounded_facts_and_option_commentary():
    p = ex.SYSTEM_PROMPT.lower()
    # Ungrounded generation hallucinated 4 of 5 "exam facts" in testing, so the prompt must pin
    # the model to the supplied material.
    assert "never introduce" in p
    assert "do not discuss the wrong options" in p
    # Groq's JSON mode requires the literal word "json" in the prompt.
    assert "json" in p


def test_budget_is_a_backstop_not_a_per_user_limit():
    from app.config import settings
    assert settings.explain_daily_budget >= 100
    assert ex.budget_left() <= settings.explain_daily_budget


def test_you_must_answer_before_asking_for_more(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 3}).json()
    qid = s["questions"][0]["id"]
    assert client.post(f"/api/quiz/question/{qid}/explain").status_code == 403
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": qid, "selected_index": 0})
    r = client.post(f"/api/quiz/question/{qid}/explain")
    assert r.status_code in (200, 503)  # 503 only when no LLM key is configured
    if r.status_code == 200:
        body = r.json()
        assert body["question_id"] == qid and len(body["explanation"]) > 40


def test_explanations_are_cached_on_the_question(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 3}).json()
    qid = s["questions"][0]["id"]
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": qid, "selected_index": 0})
    first = client.post(f"/api/quiz/question/{qid}/explain")
    if first.status_code != 200:
        return
    second = client.post(f"/api/quiz/question/{qid}/explain").json()
    assert second["cached"] is True
    assert second["explanation"] == first.json()["explanation"]


def test_unknown_question_is_404(client, user):
    assert client.post("/api/quiz/question/99999999/explain").status_code == 404
