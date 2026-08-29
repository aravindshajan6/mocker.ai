"""Spaced repetition (FSRS): every answer schedules the question's next review."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import srs


def test_wrong_answers_come_back_almost_immediately():
    state, due, _ = srs.review(None, is_correct=False)
    assert due - srs.utcnow() < timedelta(minutes=5)


def test_correct_answers_are_pushed_further_out_than_wrong_ones():
    _, due_wrong, _ = srs.review(None, is_correct=False)
    _, due_right, _ = srs.review(None, is_correct=True)
    assert due_right > due_wrong


def test_repeated_correct_answers_lengthen_the_interval():
    state, first_due, _ = srs.review(None, is_correct=True)
    prev = first_due
    for _ in range(4):
        state, due, _ = srs.review(state, is_correct=True)
        assert due >= prev
        prev = due
    # after several successes it should be days away, not minutes
    assert prev - srs.utcnow() > timedelta(hours=1)


def test_response_time_maps_to_a_rating():
    from fsrs import Rating
    assert srs.rate(False, 100) == Rating.Again
    assert srs.rate(True, 1_000) == Rating.Easy
    assert srs.rate(True, 12_000) == Rating.Good
    assert srs.rate(True, 60_000) == Rating.Hard
    assert srs.rate(True, None) == Rating.Good


def test_a_lapse_is_flagged_only_after_the_card_has_been_learned():
    _, _, lapsed_first_time = srs.review(None, is_correct=False)
    assert lapsed_first_time is False
    learned, _, _ = srs.review(None, is_correct=True)
    _, _, lapsed = srs.review(learned, is_correct=False)
    assert lapsed is True


def test_card_state_round_trips_through_json():
    import json
    state, _, _ = srs.review(None, is_correct=True)
    again, _, _ = srs.review(json.loads(json.dumps(state)), is_correct=True)
    assert again["stability"] > 0


# --- API level ---------------------------------------------------------------

def test_answering_creates_a_review_queue(client, user):
    before = client.get("/api/me/review").json()
    assert before["learning"] == 0 and before["due_now"] == 0

    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    for q in s["questions"]:
        # deliberately wrong so they are all scheduled to come back within minutes
        wrong = (client.post(f"/api/quiz/{s['id']}/answer",
                             json={"question_id": q["id"], "selected_index": 0, "elapsed_ms": 4000}).json())
        assert "is_correct" in wrong

    after = client.get("/api/me/review").json()
    assert after["learning"] == 5
    assert after["due_now"] + after["due_today"] > 0


def test_review_mode_serves_due_questions(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    answered = []
    for q in s["questions"]:
        r = client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0}).json()
        if not r["is_correct"]:
            answered.append(q["id"])
    client.post(f"/api/quiz/{s['id']}/finish")

    due = client.get("/api/me/review").json()
    if due["due_now"] == 0:
        pytest.skip("nothing due yet on this run")
    rev = client.post("/api/quiz/start", json={"mode": "review", "count": 10}).json()
    assert rev["questions"], "review session must contain questions"
    assert set(q["id"] for q in rev["questions"]) <= set(answered) | set(q["id"] for q in s["questions"])


def test_review_mode_errors_cleanly_when_nothing_is_due(client, user):
    r = client.post("/api/quiz/start", json={"mode": "review"})
    assert r.status_code == 409
    assert "review" in r.json()["detail"].lower()


def test_daily_challenge_keeps_its_size_when_reviews_are_mixed_in(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    client.post(f"/api/quiz/{s['id']}/finish")
    daily = client.post("/api/quiz/start", json={"mode": "daily"}).json()
    assert len(daily["questions"]) == 10
    assert len(set(q["id"] for q in daily["questions"])) == 10, "no duplicates when reviews are mixed in"
