"""Screen time and admin analytics.

The property that matters most is that recorded screen time can never exceed real wall-clock
time, however the client behaves — otherwise every number on the admin panel is fiction.
"""
import random
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.models import ActivityBucket, User
from app.services.analytics import credit_seconds, record_heartbeat

CAP = settings.heartbeat_seconds
T0 = datetime(2026, 9, 10, 8, 0, 0, tzinfo=timezone.utc)   # 13:30 IST


# --- crediting rules (pure) ----------------------------------------------------

def test_first_heartbeat_is_credited_one_interval():
    assert credit_seconds(None, T0) == CAP


def test_steady_pings_are_credited_their_real_gap():
    assert credit_seconds(T0, T0 + timedelta(seconds=CAP)) == CAP
    assert credit_seconds(T0, T0 + timedelta(seconds=12)) == 12


def test_a_long_absence_credits_only_the_last_interval():
    # Away for an hour: only the window the client vouched for counts, not the whole gap.
    assert credit_seconds(T0, T0 + timedelta(hours=1)) == CAP


def test_clock_skew_never_credits_negative_time():
    assert credit_seconds(T0, T0 - timedelta(seconds=5)) == 0


# --- through the database ------------------------------------------------------

@pytest.fixture
async def learner_id(db_session):
    """A throwaway learner created on the test's own loop. The sync `user` fixture can't be mixed
    with async tests: it runs asyncio.run() internally, which tears down the loop they need."""
    u = User(email=f"activity{random.randint(1, 10**9)}@example.com", name="Activity Test",
             password_hash="!")
    db_session.add(u)
    await db_session.commit()
    yield u.id
    await db_session.execute(delete(User).where(User.id == u.id))   # cascades buckets + presence
    await db_session.commit()


async def test_spam_cannot_inflate_screen_time(db_session, learner_id):
    # 50 pings inside one second: the ledger must show one interval, not 50 of them.
    for i in range(50):
        await record_heartbeat(db_session, learner_id, T0 + timedelta(milliseconds=20 * i))
    total = (await db_session.execute(
        select(ActivityBucket.seconds).where(ActivityBucket.user_id == learner_id)
    )).scalar_one()
    assert total <= CAP + 1


async def test_time_lands_in_the_ist_hour_bucket(db_session, learner_id):
    await record_heartbeat(db_session, learner_id, T0)                               # 13:30 IST
    await record_heartbeat(db_session, learner_id, T0 + timedelta(minutes=45))       # 14:15 IST
    rows = dict((await db_session.execute(
        select(ActivityBucket.hour, ActivityBucket.seconds).where(ActivityBucket.user_id == learner_id)
    )).all())
    assert rows == {13: CAP, 14: CAP}


# --- endpoints -----------------------------------------------------------------

def test_heartbeat_requires_sign_in(base_url):
    import httpx
    assert httpx.post(f"{base_url}/api/me/heartbeat").status_code == 401


def test_heartbeat_accepts_a_signed_in_user(client, user):
    assert client.post("/api/me/heartbeat").status_code == 204


def test_analytics_is_admin_only(client, user):
    assert client.get("/api/admin/analytics").status_code == 403


def test_analytics_shape_for_admin(client, admin):
    d = client.get("/api/admin/analytics?days=14").json()
    assert d["days"] == 14 and len(d["series"]) == 14
    for key in ("learners", "active_today", "active_week", "active_month",
                "screen_seconds_week", "avg_screen_seconds_week", "answers_week"):
        assert isinstance(d["summary"][key], int), key
    assert d["summary"]["active_today"] <= d["summary"]["active_week"] <= d["summary"]["active_month"]
    for cell in d["heatmap"]:
        assert 0 <= cell["dow"] <= 6 and 0 <= cell["hour"] <= 23


def test_accounts_list_carries_activity_columns(client, admin):
    rows = client.get("/api/admin/users").json()
    assert rows, "the seeded accounts should be listed"
    for key in ("screen_seconds_total", "screen_seconds_week", "active_days_month",
                "quizzes_completed", "current_streak", "total_points", "last_seen_at"):
        assert key in rows[0], key
