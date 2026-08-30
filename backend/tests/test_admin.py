"""Admin surface: closed sign-up, role separation, content jobs, questions, keys, accounts."""
import random

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import User


@pytest.fixture
def admin(client, base_url):
    """Sign the shared client in as the seeded administrator."""
    r = client.post("/api/auth/login", json={"email": settings.admin_email, "password": settings.admin_password})
    assert r.status_code == 200, "the admin account should be seeded on startup"
    assert r.json()["is_admin"] is True
    return r.json()


# --- sign-up is closed -------------------------------------------------------

def test_public_signup_is_refused(client):
    r = client.post("/api/auth/register",
                    json={"name": "Random", "email": f"rand{random.randint(1, 10**9)}@example.com",
                          "password": "secret123"})
    assert r.status_code == 403
    assert "administrator" in r.json()["detail"].lower()


def test_auth_config_reports_signup_state(client):
    assert client.get("/api/auth/config").json() == {"allow_signup": settings.allow_signup}


# --- role separation ---------------------------------------------------------

ADMIN_READS = ["/api/admin/overview", "/api/admin/users", "/api/admin/questions",
               "/api/admin/llm/keys", "/api/admin/llm/providers"]


def test_a_signed_out_visitor_cannot_reach_admin(client):
    for path in ADMIN_READS:
        assert client.get(path).status_code == 401


def test_an_ordinary_user_cannot_reach_admin(client, user):
    assert client.get("/api/auth/me").json()["is_admin"] is False
    for path in ADMIN_READS:
        assert client.get(path).status_code == 403, path


def test_an_ordinary_user_cannot_change_content(client, user):
    assert client.post("/api/admin/content/current-affairs/run").status_code == 403
    assert client.post("/api/admin/content/audit/run").status_code == 403
    assert client.post("/api/admin/questions", json={
        "topic": "kerala", "question": "A question long enough to pass validation",
        "options": ["a", "b", "c", "d"], "answer": 0}).status_code == 403
    assert client.post("/api/admin/llm/keys", json={
        "label": "x", "provider": "groq", "api_key": "x" * 20}).status_code == 403
    assert client.post("/api/admin/users", json={
        "name": "X", "email": "x@example.com", "password": "secret123"}).status_code == 403


def test_admin_can_read_the_overview(client, admin):
    o = client.get("/api/admin/overview").json()
    assert o["users"] >= 1 and o["admins"] >= 1
    assert o["questions_active"] > 1000
    assert "seed" in o["questions_by_source"]
    assert isinstance(o["llm_keys_active"], int)


# --- questions ---------------------------------------------------------------

def test_admin_can_add_a_question_and_learners_can_answer_it(client, admin):
    stem = f"Which body issues the Kerala PSC notification number {random.randint(1, 10**9)}?"
    r = client.post("/api/admin/questions", json={
        "topic": "kerala", "question": stem,
        "options": ["Kerala PSC", "UPSC", "SSC", "RRB"], "answer": 0,
        "explanation": "The Kerala Public Service Commission issues its own notifications.",
        "difficulty": 1, "tags": ["admin-test"]})
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["source"] == "admin" and q["is_active"] is True

    # duplicates and malformed options are refused
    assert client.post("/api/admin/questions", json={
        "topic": "kerala", "question": stem, "options": ["a", "b", "c", "d"], "answer": 0}).status_code == 409
    assert client.post("/api/admin/questions", json={
        "topic": "kerala", "question": "Another perfectly valid stem here",
        "options": ["same", "same", "c", "d"], "answer": 0}).status_code == 422
    assert client.post("/api/admin/questions", json={
        "topic": "not-a-topic", "question": "Another perfectly valid stem here",
        "options": ["a", "b", "c", "d"], "answer": 0}).status_code == 404

    # retiring takes it out of circulation without deleting it
    assert client.post(f"/api/admin/questions/{q['id']}/toggle").json()["is_active"] is False
    assert client.post(f"/api/admin/questions/{q['id']}/toggle").json()["is_active"] is True


def test_question_search_and_filters(client, admin):
    all_q = client.get("/api/admin/questions?limit=5").json()
    assert all_q["total"] > 1000 and len(all_q["questions"]) == 5
    flagged = client.get("/api/admin/questions?only=flagged").json()
    for row in flagged["questions"]:
        assert row["verdict"] in ("wrong_answer", "ambiguous")
    inactive = client.get("/api/admin/questions?only=inactive&limit=3").json()
    assert all(not r["is_active"] for r in inactive["questions"])


# --- accounts ----------------------------------------------------------------

def test_admin_provisions_accounts_that_can_sign_in(client, admin, base_url):
    import httpx
    email = f"pytest-prov{random.randint(1, 10**9)}@example.com"
    u = client.post("/api/admin/users", json={"name": "Provisioned", "email": email,
                                              "password": "secret123", "is_admin": False}).json()
    with httpx.Client(base_url=base_url, timeout=30) as fresh:
        me = fresh.post("/api/auth/login", json={"email": email, "password": "secret123"})
        assert me.status_code == 200 and me.json()["is_admin"] is False
        assert fresh.get("/api/admin/overview").status_code == 403

    assert client.post("/api/admin/users", json={"name": "Dup", "email": email,
                                                 "password": "secret123"}).status_code == 409
    assert client.post(f"/api/admin/users/{u['id']}/password", json={"password": "newsecret"}).status_code == 200
    assert client.delete(f"/api/admin/users/{u['id']}").status_code == 200


def test_admin_cannot_delete_their_own_account(client, admin):
    assert client.delete(f"/api/admin/users/{admin['id']}").status_code == 409


# --- LLM keys ----------------------------------------------------------------

def test_keys_are_never_returned_in_full(client, admin):
    secret = "gsk_" + "z" * 40
    created = client.post("/api/admin/llm/keys", json={
        "label": "Test key", "provider": "groq", "api_key": secret, "priority": 900}).json()
    try:
        assert secret not in str(created)
        assert created["api_key_masked"].endswith(secret[-4:])
        listing = client.get("/api/admin/llm/keys")
        assert secret not in listing.text, "a full key must never reach the browser"
    finally:
        client.delete(f"/api/admin/llm/keys/{created['id']}")


def test_key_lifecycle(client, admin):
    created = client.post("/api/admin/llm/keys", json={
        "label": "Lifecycle", "provider": "groq", "api_key": "gsk_" + "y" * 40, "priority": 950}).json()
    kid = created["id"]
    try:
        assert client.post("/api/admin/llm/keys", json={
            "label": "Dup", "provider": "groq", "api_key": "gsk_" + "y" * 40}).status_code == 409
        assert client.post("/api/admin/llm/keys", json={
            "label": "Bad", "provider": "nope", "api_key": "x" * 20}).status_code == 422
        assert client.patch("/api/admin/llm/keys/" + str(kid), json={"is_active": False}).json()["is_active"] is False
        assert client.patch("/api/admin/llm/keys/" + str(kid), json={"priority": 5}).json()["priority"] == 5
    finally:
        assert client.delete(f"/api/admin/llm/keys/{kid}").status_code == 200
    assert client.delete(f"/api/admin/llm/keys/{kid}").status_code == 404


def test_a_rejected_key_disables_itself(client, admin):
    """A key the provider refuses should stop being tried, not fail every job forever."""
    created = client.post("/api/admin/llm/keys", json={
        "label": "Invalid", "provider": "groq", "api_key": "gsk_" + "0" * 40, "priority": 999}).json()
    try:
        result = client.post(f"/api/admin/llm/keys/{created['id']}/test").json()
        if result["ok"]:
            pytest.skip("no network to the provider in this environment")
        assert client.get("/api/admin/llm/keys").json()
        row = next(k for k in client.get("/api/admin/llm/keys").json() if k["id"] == created["id"])
        assert row["is_active"] is False
        assert row["last_error"]
    finally:
        client.delete(f"/api/admin/llm/keys/{created['id']}")


async def test_seeded_accounts_exist(db_session):
    for email, is_admin in ((settings.admin_email, True), (settings.seed_user_email, False)):
        u = (await db_session.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
        assert u is not None, f"{email} should be provisioned at startup"
        assert u.is_admin is is_admin
