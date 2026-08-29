"""End-to-end API tests for the quiz lifecycle."""
import pytest


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/topics").status_code == 401
    assert client.post("/api/quiz/start", json={"mode": "mixed"}).status_code == 401


def test_register_login_logout(client, user):
    assert client.get("/api/auth/me").json()["email"] == user["email"]
    assert client.post("/api/auth/register",
                       json={"name": "Dup", "email": user["email"], "password": "secret123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "nope"}).status_code == 401
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_topics_have_questions(client, user):
    topics = client.get("/api/topics").json()
    assert len(topics) >= 5
    assert all(t["question_count"] > 0 for t in topics)
    assert {"indian-history", "kerala", "indian-polity"} <= {t["slug"] for t in topics}


def test_daily_quiz_is_resumable_and_scored_once(client, user):
    s = client.post("/api/quiz/start", json={"mode": "daily"}).json()
    assert len(s["questions"]) == 10
    assert client.post("/api/quiz/start", json={"mode": "daily"}).json()["id"] == s["id"], "daily must resume"

    for q in s["questions"]:
        r = client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["correct_index"] <= 3
        # answering the same question twice is rejected
        assert client.post(f"/api/quiz/{s['id']}/answer",
                           json={"question_id": q["id"], "selected_index": 1}).status_code == 409

    fin = client.post(f"/api/quiz/{s['id']}/finish").json()
    assert fin["bonus"] >= 25 and fin["total"] == 10 and not fin["already_finished"]
    assert "first-quiz" in fin["new_badges"]
    assert client.post(f"/api/quiz/{s['id']}/finish").json()["already_finished"] is True
    daily = client.get("/api/quiz/daily").json()
    assert daily["done"] and daily["score"] == fin["score"]


def test_answers_are_scored_correctly(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    q = s["questions"][0]
    first = client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0}).json()
    if first["is_correct"]:
        assert first["points"] > 0 and first["combo"] == 1
    else:
        assert first["points"] == 0 and first["combo"] == 0
    assert first["streak"] == 1 and first["streak_extended"] is True
    assert first["explanation"]


def test_topic_quiz_and_abandon(client, user):
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "kerala"}).json()
    assert s["topic"] == "Kerala"
    assert client.post(f"/api/quiz/{s['id']}/abandon").status_code == 200
    assert client.get(f"/api/quiz/{s['id']}").status_code == 404
    assert client.post("/api/quiz/start", json={"mode": "topic", "topic": "nope"}).status_code == 404


def test_unfinished_quiz_is_listed_as_active(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    active = client.get("/api/quiz/active").json()
    assert s["id"] in [a["id"] for a in active]
    assert active[0]["total"] == 5


def test_cannot_finish_a_partially_answered_quiz(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": s["questions"][0]["id"], "selected_index": 0})
    assert client.post(f"/api/quiz/{s['id']}/finish").status_code == 409


def test_another_users_quiz_is_not_reachable(client, user, base_url):
    import httpx
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    with httpx.Client(base_url=base_url, timeout=30) as other:
        other.post("/api/auth/register", json={"name": "Other", "email": f"other{s['id']}@example.com",
                                               "password": "secret123"})
        assert other.get(f"/api/quiz/{s['id']}").status_code == 404
        assert other.post(f"/api/quiz/{s['id']}/answer",
                          json={"question_id": s["questions"][0]["id"], "selected_index": 0}).status_code == 404


def test_stats_and_history_reflect_activity(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    client.post(f"/api/quiz/{s['id']}/finish")
    st = client.get("/api/me/stats").json()
    assert st["questions_answered"] == 5 and st["quizzes_completed"] == 1
    assert st["current_streak"] == 1 and st["last_7_days"][-1]["answered"] == 5
    assert st["level"] >= 1 and st["badge_meta"]
    hist = client.get("/api/me/history").json()
    assert len(hist) == 1 and hist[0]["total"] == 5
    assert any(r["is_me"] for r in client.get("/api/me/leaderboard").json())


@pytest.mark.parametrize("payload", [
    {"mode": "nonsense"},
    {"mode": "topic"},                      # topic slug missing
    {"mode": "mixed", "count": 999},
])
def test_bad_start_payloads_are_rejected(client, user, payload):
    assert client.post("/api/quiz/start", json=payload).status_code in (404, 422)
