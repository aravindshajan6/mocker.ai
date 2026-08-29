"""Regression tests for the issues found in the security review."""
import concurrent.futures as cf

import httpx
import pytest


def _exam(client):
    return client.post("/api/exam/start", json={"count": 10, "duration_minutes": 30}).json()


def test_the_quiz_router_will_not_serve_an_exam(client, user):
    """The quiz session response includes correct_index for answered questions. Reachable during a
    live exam it would hand the candidate the whole answer key."""
    ex = _exam(client)
    for q in ex["questions"][:3]:
        client.post(f"/api/exam/{ex['id']}/answer", json={"question_id": q["id"], "selected_index": 0})

    assert client.get(f"/api/quiz/{ex['id']}").status_code == 404
    leak = client.post(f"/api/quiz/{ex['id']}/answer",
                       json={"question_id": ex["questions"][0]["id"], "selected_index": 1})
    assert leak.status_code == 404
    assert "correct_index" not in leak.text
    assert client.post(f"/api/quiz/{ex['id']}/finish").status_code == 404
    assert client.post(f"/api/quiz/{ex['id']}/abandon").status_code == 404


def test_parallel_exam_submits_score_once(client, user, base_url):
    ex = _exam(client)
    for q in ex["questions"]:
        client.post(f"/api/exam/{ex['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    cookies = dict(client.cookies)

    def submit():
        with httpx.Client(base_url=base_url, cookies=cookies, timeout=60) as c:
            return c.post(f"/api/exam/{ex['id']}/submit").status_code

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        assert all(s == 200 for s in pool.map(lambda _: submit(), range(6)))

    st = client.get("/api/me/stats").json()
    assert st["quizzes_completed"] == 1, "a race must not count the same paper repeatedly"
    assert st["questions_answered"] == 10


def test_parallel_quiz_finishes_award_the_bonus_once(client, user, base_url):
    s = client.post("/api/quiz/start", json={"mode": "daily"}).json()
    for q in s["questions"]:
        client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": q["id"], "selected_index": 0})
    cookies = dict(client.cookies)

    def finish():
        with httpx.Client(base_url=base_url, cookies=cookies, timeout=60) as c:
            return c.post(f"/api/quiz/{s['id']}/finish").json()

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: finish(), range(8)))

    assert sum(1 for r in results if not r["already_finished"]) == 1
    assert client.get("/api/me/stats").json()["quizzes_completed"] == 1


def test_parallel_duplicate_answers_return_409_not_500(client, user, base_url):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 5}).json()
    qid = s["questions"][0]["id"]
    cookies = dict(client.cookies)

    def answer():
        with httpx.Client(base_url=base_url, cookies=cookies, timeout=60) as c:
            return c.post(f"/api/quiz/{s['id']}/answer", json={"question_id": qid, "selected_index": 0}).status_code

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(lambda _: answer(), range(6)))

    assert 200 in codes
    assert all(c in (200, 409) for c in codes), f"no 500s expected, got {codes}"
    assert codes.count(200) == 1


def test_registration_creates_the_preferences_row(client, user):
    """Reminders are opt-out, so the row has to exist or the reminder job's join skips the user."""
    p = client.get("/api/me/prefs").json()
    assert p["reminders_enabled"] is True


async def test_reminder_pass_covers_users_with_no_prefs_row(db_session):
    """Accounts created before prefs existed must still be reachable."""
    from sqlalchemy import func, select
    from app.content import reminders
    from app.models import User, UserPrefs

    users = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    prefs = (await db_session.execute(select(func.count()).select_from(UserPrefs))).scalar_one()
    assert users >= prefs
    summary = await reminders.run(db_session)      # must not raise on rows with no prefs
    assert "considered" in summary


def test_admin_endpoints_reject_wrong_tokens(client, user):
    for hdr in ({}, {"X-Admin-Token": ""}, {"X-Admin-Token": "wrong"}):
        assert client.get("/api/admin/verification", headers=hdr).status_code == 403
        assert client.post("/api/admin/current-affairs/run", headers=hdr).status_code == 403


def test_auditor_prompt_marks_dataset_text_as_data():
    from app.content import verify
    p = verify.SYSTEM_PROMPT
    assert "<<<ITEM>>>" in p and "<<<END>>>" in p
    assert "not a request" in p.lower() or "ignore it" in p.lower()
