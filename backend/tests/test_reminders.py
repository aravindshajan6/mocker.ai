"""Daily reminders: timing rules, channel handling and copy."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.content import reminders
from app.models import UserPrefs

IST = ZoneInfo("Asia/Kolkata")


def prefs_at(hour: int, minute: int = 0, tz: str = "Asia/Kolkata", last=None) -> UserPrefs:
    return UserPrefs(user_id="u", reminders_enabled=True, reminder_hour=hour,
                     reminder_minute=minute, timezone=tz, last_reminded_on=last)


def utc(y, m, d, hh, mm, tz=IST):
    return datetime(y, m, d, hh, mm, tzinfo=tz).astimezone(ZoneInfo("UTC"))


def test_fires_inside_the_window_after_the_chosen_time():
    p = prefs_at(19, 0)
    assert reminders._due_now(p, utc(2026, 8, 30, 19, 0)) is True
    assert reminders._due_now(p, utc(2026, 8, 30, 19, 15)) is True


def test_does_not_fire_before_the_chosen_time():
    p = prefs_at(19, 0)
    assert reminders._due_now(p, utc(2026, 8, 30, 18, 45)) is False


def test_does_not_fire_long_after_the_window_closed():
    """A missed window is missed — nobody wants a 'study now' ping at midnight."""
    p = prefs_at(19, 0)
    assert reminders._due_now(p, utc(2026, 8, 30, 23, 30)) is False


def test_never_sends_twice_on_the_same_day():
    p = prefs_at(19, 0, last=datetime(2026, 8, 30, tzinfo=IST).date())
    assert reminders._due_now(p, utc(2026, 8, 30, 19, 5)) is False
    # ...but the next day is fine again
    assert reminders._due_now(p, utc(2026, 8, 31, 19, 5)) is True


def test_the_users_own_timezone_decides_when_it_is_seven_pm():
    london = prefs_at(19, 0, tz="Europe/London")
    # 19:00 in London is not 19:00 in Kolkata
    assert reminders._due_now(london, utc(2026, 8, 30, 19, 0, tz=IST)) is False
    assert reminders._due_now(london, datetime(2026, 8, 30, 19, 0, tzinfo=ZoneInfo("Europe/London")).astimezone(ZoneInfo("UTC"))) is True


def test_a_broken_timezone_does_not_break_reminders():
    p = prefs_at(19, 0, tz="Not/AZone")
    assert reminders._due_now(p, utc(2026, 8, 30, 19, 5)) is True  # falls back to IST


def test_copy_never_guilts_the_reader():
    everything = " ".join(t + " " + b for t, b in reminders.LINES + reminders.STREAK_LINES).lower()
    for word in ("don't lose", "disappointed", "sad", "failed", "you missed", "shame"):
        assert word not in everything


def test_streak_copy_is_only_used_once_a_streak_exists():
    title, body = reminders._pick(streak=0, seed=1)
    assert "{streak}" not in title and "{streak}" not in body
    assert not any(title == t.format(streak=0) for t, _ in reminders.STREAK_LINES)


def test_copy_is_deterministic_for_a_given_day_and_user():
    a = reminders._pick(5, seed=42)
    b = reminders._pick(5, seed=42)
    assert a == b


async def test_reminder_pass_is_safe_to_run_with_no_subscribers(db_session):
    summary = await reminders.run(db_session)
    assert set(summary) >= {"considered", "sent_push", "sent_telegram"}


async def test_prefs_endpoint_round_trips(client, user):
    p = client.get("/api/me/prefs").json()
    assert p["reminders_enabled"] is True and p["vapid_public_key"]
    assert len(p["vapid_public_key"]) > 80, "application server key must be a real P-256 point"

    updated = client.put("/api/me/prefs", json={"reminder_hour": 7, "reminder_minute": 30,
                                                "timezone": "Asia/Kolkata"}).json()
    assert updated["reminder_hour"] == 7 and updated["reminder_minute"] == 30
    assert client.get("/api/me/prefs").json()["reminder_hour"] == 7


async def test_bad_timezone_is_rejected(client, user):
    assert client.put("/api/me/prefs", json={"timezone": "Mars/Olympus"}).status_code == 422


async def test_push_subscription_round_trips(client, user):
    sub = {"endpoint": f"https://push.example.com/{user['id']}", "p256dh": "BKxQ" + "a" * 60, "auth": "c" * 22}
    out = client.post("/api/me/push/subscribe", json=sub).json()
    assert out["push_devices"] == 1
    # subscribing the same endpoint again must not duplicate the device
    assert client.post("/api/me/push/subscribe", json=sub).json()["push_devices"] == 1
    assert client.post("/api/me/push/unsubscribe", json=sub).json()["push_devices"] == 0


async def test_test_push_without_a_device_is_a_clean_error(client, user):
    assert client.post("/api/me/push/test").status_code == 409
