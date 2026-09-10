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


def test_accounts_list_carries_activity_columns(client, admin):
    rows = client.get("/api/admin/users").json()
    assert rows, "the seeded accounts should be listed"
    for key in ("screen_seconds_total", "screen_seconds_week", "active_days_month",
                "quizzes_completed", "current_streak", "total_points", "last_seen_at"):
        assert key in rows[0], key


def test_dashboard_is_admin_only(client, user):
    assert client.get("/api/admin/analytics/dashboard").status_code == 403


def test_dashboard_shape_and_ranges(client, admin):
    for days in (7, 30, 90):
        d = client.get(f"/api/admin/analytics/dashboard?days={days}").json()
        assert d["range"]["days"] == days and len(d["current"]["series"]) == days
        for key in ("active", "avg_daily_active", "screen_seconds", "answers", "quizzes", "new_users"):
            assert key in d["current"]["totals"] and key in d["previous"], key
        for section in ("topics", "difficulty", "sources", "modes", "heatmap", "hardest",
                        "top_learners", "streaks", "cohorts"):
            assert isinstance(d[section], list), section
        assert len(d["exams"]["distribution"]) == 11          # <0 plus ten 10-point bins
        assert sum(b["users"] for b in d["streaks"]) == d["learners"]


def test_dashboard_rejects_odd_ranges_by_falling_back(client, admin):
    assert client.get("/api/admin/analytics/dashboard?days=13").json()["range"]["days"] == 30
