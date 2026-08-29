"""Weak-topic analytics and targeted practice."""


def test_insights_are_honest_when_there_is_no_data_yet(client, user):
    ins = client.get("/api/me/insights").json()
    assert ins["answered_total"] == 0
    assert ins["enough_data"] is False
    assert ins["weakest"] == [] and ins["strongest"] == []
    assert len(ins["untouched"]) >= 5
    assert "few more questions" in ins["headline"].lower()
    assert all(t["trend"] == "new" for t in ins["topics"])


def test_a_topic_needs_enough_attempts_before_it_is_called_weak(client, user):
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "kerala", "count": 5}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    ins = client.get("/api/me/insights").json()
    kerala = next(t for t in ins["topics"] if t["slug"] == "kerala")
    assert kerala["answered"] == 5
    # 5 attempts is below the threshold, so no verdict is drawn from it
    assert kerala["recent_accuracy"] is None
    assert "kerala" not in ins["weakest"]


def test_insights_track_accuracy_and_coverage(client, user):
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "geography", "count": 10}).json()
    correct = 0
    for q in s["questions"]:
        r = client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0}).json()
        correct += 1 if r["is_correct"] else 0
    ins = client.get("/api/me/insights").json()
    geo = next(t for t in ins["topics"] if t["slug"] == "geography")
    assert geo["answered"] == 10 and geo["correct"] == correct
    assert geo["accuracy"] == round(correct / 10, 4)
    assert geo["recent_accuracy"] is not None and geo["trend"] in ("steady", "improving", "slipping")
    assert 0 < geo["coverage"] <= 1
    assert ins["answered_total"] == 10


def test_weak_mode_builds_a_practice_set(client, user):
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "economy", "count": 10}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    client.post(f"/api/quiz/{s['id']}/finish")

    weak = client.post("/api/quiz/start", json={"mode": "weak", "count": 10}).json()
    assert len(weak["questions"]) == 10
    assert len({q["id"] for q in weak["questions"]}) == 10, "no duplicates"


def test_weak_mode_falls_back_gracefully_with_no_history(client, user):
    """A brand new user asking for weak-topic practice should still get a usable set."""
    weak = client.post("/api/quiz/start", json={"mode": "weak", "count": 8}).json()
    assert len(weak["questions"]) == 8
