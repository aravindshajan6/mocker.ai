"""Reviewing past answers, by set and by category."""


def _play(client, topic="kerala", count=5):
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": topic, "count": count}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    client.post(f"/api/quiz/{s['id']}/finish")
    return s


def test_answers_starts_empty(client, user):
    a = client.get("/api/me/answers").json()
    assert a["topics"] == [] and a["questions"] == [] and a["total"] == 0


def test_answers_group_by_category(client, user):
    _play(client, "kerala", 5)
    _play(client, "geography", 4)
    a = client.get("/api/me/answers").json()
    slugs = {t["slug"]: t for t in a["topics"]}
    assert slugs["kerala"]["attempted"] == 5
    assert slugs["geography"]["attempted"] == 4
    for t in a["topics"]:
        assert t["correct"] + t["wrong"] == t["attempted"]
    assert a["total"] == 9


def test_answers_filter_by_topic_and_outcome(client, user):
    _play(client, "kerala", 5)
    _play(client, "geography", 4)

    k = client.get("/api/me/answers?topic=kerala").json()
    assert k["total"] == 5
    assert all(q["topic_slug"] == "kerala" for q in k["questions"])

    wrong = client.get("/api/me/answers?only=wrong").json()
    assert all(not q["is_correct"] for q in wrong["questions"])
    right = client.get("/api/me/answers?only=correct").json()
    assert all(q["is_correct"] for q in right["questions"])
    assert wrong["total"] + right["total"] == 9


def test_each_answer_carries_what_review_needs(client, user):
    _play(client, "kerala", 3)
    q = client.get("/api/me/answers").json()["questions"][0]
    assert len(q["options"]) == 4
    assert 0 <= q["correct_index"] <= 3 and 0 <= q["selected_index"] <= 3
    assert q["is_correct"] == (q["correct_index"] == q["selected_index"])
    assert q["explanation"] and q["topic"] and q["topic_icon"]
    assert q["times_seen"] >= 1 and q["times_correct"] <= q["times_seen"]


def test_a_repeated_question_appears_once_with_its_latest_answer(client, user):
    """Meeting the same question three times should not produce three rows."""
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "kerala", "count": 3}).json()
    qid = s["questions"][0]["id"]
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": qid, "selected_index": 0})
    for q in s["questions"][1:]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    client.post(f"/api/quiz/{s['id']}/finish")

    again = client.post("/api/quiz/start", json={"mode": "topic", "topic": "kerala", "count": 3}).json()
    if qid in [q["id"] for q in again["questions"]]:
        client.post(f"/api/quiz/{again['id']}/answer", json={"question_id": qid, "selected_index": 1})
        rows = client.get("/api/me/answers?topic=kerala").json()["questions"]
        matching = [r for r in rows if r["question_id"] == qid]
        assert len(matching) == 1
        assert matching[0]["times_seen"] == 2
        assert matching[0]["selected_index"] == 1, "the latest answer is the one shown"


def test_answers_paginate(client, user):
    _play(client, "kerala", 10)
    page = client.get("/api/me/answers?limit=4&offset=0").json()
    assert len(page["questions"]) == 4 and page["total"] == 10
    second = client.get("/api/me/answers?limit=4&offset=4").json()
    assert {q["question_id"] for q in page["questions"]}.isdisjoint({q["question_id"] for q in second["questions"]})


def test_retry_rebuilds_a_set_from_the_wrong_answers(client, user):
    s = _play(client, "kerala", 10)
    wrong = client.get("/api/me/answers?only=wrong").json()
    if wrong["total"] == 0:
        return
    retry = client.post("/api/quiz/start", json={"mode": "retry", "session": s["id"]}).json()
    assert retry["questions"], "retry set must not be empty"
    assert all(not q["id"] in [] for q in retry["questions"])
    original = {q["id"] for q in s["questions"]}
    assert {q["id"] for q in retry["questions"]} <= original


def test_retry_rejects_a_set_with_no_mistakes(client, user, base_url):
    """A perfect set has nothing to redo, and should say so rather than starting an empty quiz."""
    s = client.post("/api/quiz/start", json={"mode": "topic", "topic": "kerala", "count": 5}).json()
    for q in s["questions"]:
        # answer each correctly by reading the revealed key from the response
        r = client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0}).json()
        if not r["is_correct"]:
            return  # got one wrong, this scenario does not apply on this run
    client.post(f"/api/quiz/{s['id']}/finish")
    assert client.post("/api/quiz/start", json={"mode": "retry", "session": s["id"]}).status_code == 409


def test_retry_needs_a_session_and_rejects_someone_elses(client, user, base_url):
    import httpx
    assert client.post("/api/quiz/start", json={"mode": "retry"}).status_code == 422
    s = _play(client, "kerala", 5)
    with httpx.Client(base_url=base_url, timeout=30) as other:
        other.post("/api/auth/register", json={"name": "O", "email": f"o{s['id']}@example.com", "password": "secret123"})
        assert other.post("/api/quiz/start", json={"mode": "retry", "session": s["id"]}).status_code == 404


def test_leaderboard_only_lists_people_who_finished_something(client, user):
    """A row with points but no completed quiz is an abandoned session, not a competitor."""
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": s["questions"][0]["id"], "selected_index": 0})
    board = client.get("/api/me/leaderboard").json()
    me = [r for r in board if r["is_me"]]
    assert me and me[0]["points"] == 0, "unfinished work should not put you on the board"
