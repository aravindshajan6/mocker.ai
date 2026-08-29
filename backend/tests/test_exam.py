"""Exam mode: real-format mock papers with negative marking."""
import pytest

from app.services import scoring


def test_negative_marking_matches_the_commission_rules():
    assert scoring.exam_raw_score(60, 30) == pytest.approx(50.0, abs=0.01)
    assert scoring.exam_raw_score(0, 3) == pytest.approx(-1.0, abs=0.01)
    assert scoring.exam_raw_score(10, 0) == 10.0


def test_a_blind_guess_is_exactly_break_even_with_four_options():
    # 1/4 chance of +1, 3/4 chance of -1/3 => 0. This is the fact exam mode teaches.
    assert scoring.guess_break_even(4) == 0.0
    # Eliminate one option and guessing becomes profitable.
    assert scoring.guess_break_even(3) > 0


def test_exam_points_never_go_negative():
    assert scoring.exam_points(0, 50, 100) == 0
    assert scoring.exam_points(10, 0, 100) == 100


@pytest.fixture
def exam(client, user):
    return client.post("/api/exam/start", json={"count": 25, "duration_minutes": 19}).json()


def test_start_sets_a_server_side_deadline(client, user, exam):
    assert exam["total"] == 25 and exam["submitted"] is False
    assert 1100 < exam["seconds_remaining"] <= 19 * 60
    assert exam["duration_seconds"] == 19 * 60


def test_starting_again_resumes_the_running_paper(client, user, exam):
    again = client.post("/api/exam/start", json={"count": 100}).json()
    assert again["id"] == exam["id"]
    assert client.get("/api/exam/current").json()["id"] == exam["id"]


def test_answers_never_leak_correctness_during_the_exam(client, user, exam):
    q = exam["questions"][0]
    r = client.post(f"/api/exam/{exam['id']}/answer",
                    json={"question_id": q["id"], "selected_index": 2, "marked_for_review": True})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"ok", "answered", "seconds_remaining"}
    assert "is_correct" not in r.text and "correct_index" not in r.text


def test_answers_can_be_changed_and_cleared(client, user, exam):
    q = exam["questions"][0]
    client.post(f"/api/exam/{exam['id']}/answer", json={"question_id": q["id"], "selected_index": 1})
    client.post(f"/api/exam/{exam['id']}/answer", json={"question_id": q["id"], "selected_index": 3})
    state = client.get(f"/api/exam/{exam['id']}").json()
    assert state["answers"][str(q["id"])] == 3
    client.post(f"/api/exam/{exam['id']}/answer", json={"question_id": q["id"], "selected_index": -1})
    assert client.get(f"/api/exam/{exam['id']}").json()["answers"][str(q["id"])] == -1


def test_marking_for_review_round_trips(client, user, exam):
    q = exam["questions"][2]
    client.post(f"/api/exam/{exam['id']}/answer",
                json={"question_id": q["id"], "selected_index": 0, "marked_for_review": True})
    assert client.get(f"/api/exam/{exam['id']}").json()["marked"] == [q["id"]]


def test_submit_grades_the_paper_and_locks_it(client, user, exam):
    for i, q in enumerate(exam["questions"][:10]):
        client.post(f"/api/exam/{exam['id']}/answer", json={"question_id": q["id"], "selected_index": i % 4})
    res = client.post(f"/api/exam/{exam['id']}/submit").json()

    assert res["total"] == 25
    assert res["attempted"] == 10 and res["blank"] == 15
    assert res["correct"] + res["wrong"] == res["attempted"]
    assert res["raw_score"] == pytest.approx(res["correct"] - res["wrong"] / 3, abs=0.01)
    assert res["marks_lost_to_negative"] == pytest.approx(res["wrong"] / 3, abs=0.01)
    assert len(res["review"]) == 25
    assert sum(1 for r in res["review"] if r["skipped"]) == 15
    assert res["coaching"] and res["per_topic"]

    # locked afterwards, and re-submitting is idempotent
    assert client.post(f"/api/exam/{exam['id']}/submit").json()["raw_score"] == res["raw_score"]
    assert client.post(f"/api/exam/{exam['id']}/answer",
                       json={"question_id": exam["questions"][0]["id"], "selected_index": 1}).status_code == 409
    assert client.get("/api/exam/current").json() is None


def test_blank_answers_carry_no_penalty(client, user, exam):
    """A paper with nothing attempted must score exactly zero, not a negative."""
    res = client.post(f"/api/exam/{exam['id']}/submit").json()
    assert res["attempted"] == 0 and res["blank"] == 25
    assert res["raw_score"] == 0.0 and res["marks_lost_to_negative"] == 0.0
    assert res["points"] == 0


def test_stats_count_only_attempted_questions(client, user, exam):
    for q in exam["questions"][:4]:
        client.post(f"/api/exam/{exam['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    res = client.post(f"/api/exam/{exam['id']}/submit").json()
    st = client.get("/api/me/stats").json()
    assert st["questions_answered"] == 4 == res["attempted"]
    assert st["quizzes_completed"] == 1


def test_another_users_exam_is_not_reachable(client, user, exam, base_url):
    import httpx
    with httpx.Client(base_url=base_url, timeout=30) as other:
        other.post("/api/auth/register", json={"name": "O", "email": f"o{exam['id']}@x.com", "password": "secret123"})
        assert other.get(f"/api/exam/{exam['id']}").status_code == 404
        assert other.post(f"/api/exam/{exam['id']}/submit").status_code == 404
