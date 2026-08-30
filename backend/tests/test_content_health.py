"""Health of the daily current-affairs pull, and the retry policy behind it."""
from datetime import date, timedelta

import pytest
from sqlalchemy import delete

from app.config import settings
from app.content.current_affairs import RETRY_BACKOFF_MINUTES, day_health, should_run_now
from app.models import ContentRun, utcnow
from app.services.quiz import IST

EMPTY_DAY = date(2019, 3, 14)   # far enough back that no real questions exist for it


@pytest.fixture
async def clean_day(db_session):
    async def purge():
        await db_session.execute(delete(ContentRun).where(ContentRun.day == EMPTY_DAY))
        await db_session.commit()
    await purge()
    yield db_session
    await purge()


async def test_a_day_with_no_questions_is_not_healthy(clean_day):
    h = await day_health(clean_day, EMPTY_DAY)
    assert h.healthy is False and h.questions == 0
    assert h.attempts == 0 and h.next_retry_at is None and h.exhausted is False


async def test_health_is_judged_on_questions_not_on_a_reported_success(clean_day):
    """A run can finish 'ok' having inserted nothing; that day still needs another attempt."""
    clean_day.add(ContentRun(day=EMPTY_DAY, status="ok", message="inserted 0", attempt=1,
                             finished_at=utcnow()))
    await clean_day.commit()
    h = await day_health(clean_day, EMPTY_DAY)
    assert h.last_status == "ok"
    assert h.healthy is False, "no questions means the day is not done, whatever the run said"


async def test_retries_back_off_and_then_give_up(clean_day):
    previous = 0.0
    for attempt in range(1, len(RETRY_BACKOFF_MINUTES) + 1):
        clean_day.add(ContentRun(day=EMPTY_DAY, status="error", message=f"boom {attempt}",
                                 attempt=attempt, finished_at=utcnow()))
        await clean_day.commit()
        h = await day_health(clean_day, EMPTY_DAY)
        assert h.attempts == attempt
        gap = (h.next_retry_at - h.last_attempt_at).total_seconds() / 60
        assert gap == RETRY_BACKOFF_MINUTES[attempt - 1]
        assert gap >= previous, "each retry should wait at least as long as the last"
        previous = gap

    # one more failure exhausts the allowance
    clean_day.add(ContentRun(day=EMPTY_DAY, status="error", message="final",
                             attempt=len(RETRY_BACKOFF_MINUTES) + 1, finished_at=utcnow()))
    await clean_day.commit()
    h = await day_health(clean_day, EMPTY_DAY)
    assert h.exhausted is True and h.next_retry_at is None


async def test_skipped_runs_do_not_count_as_attempts(clean_day):
    for _ in range(3):
        clean_day.add(ContentRun(day=EMPTY_DAY, status="skipped", message="already done",
                                 finished_at=utcnow()))
    await clean_day.commit()
    assert (await day_health(clean_day, EMPTY_DAY)).attempts == 0


async def test_supervisor_waits_until_the_scheduled_hour(db_session):
    from datetime import datetime
    early = datetime.now(IST).replace(hour=max(0, settings.current_affairs_hour_ist - 1), minute=0)
    due, why = await should_run_now(db_session, early)
    if (await day_health(db_session, early.date())).healthy:
        assert due is False and "already published" in why
    else:
        assert due is False and "waiting for" in why


async def test_supervisor_does_not_rerun_a_healthy_day(db_session):
    from datetime import datetime
    today_health = await day_health(db_session)
    if not today_health.healthy:
        pytest.skip("today has not been generated in this environment")
    due, why = await should_run_now(db_session, datetime.now(IST))
    assert due is False and "already published" in why


def test_health_endpoint_is_admin_only(client, user):
    assert client.get("/api/admin/content/health").status_code == 403


def test_health_endpoint_reports_the_window(client, admin):
    h = client.get("/api/admin/content/health").json()
    assert h["scheduled_hour_ist"] == settings.current_affairs_hour_ist
    assert h["min_questions"] == settings.current_affairs_min_questions
    assert h["max_attempts"] == settings.current_affairs_max_attempts
    assert len(h["recent"]) == 7
    assert h["today"]["day"] == h["recent"][0]["day"]
    assert isinstance(h["due_now"], bool) and h["reason"]


def test_health_endpoint_accepts_a_window(client, admin):
    assert len(client.get("/api/admin/content/health?days=14").json()["recent"]) == 14
    assert len(client.get("/api/admin/content/health?days=999").json()["recent"]) == 30
