"""Streaks: repairs for a missed day, and milestone celebrations."""
from datetime import date, timedelta

import pytest

from app.models import UserStats
from app.services import scoring
from app.services.quiz import touch_streak

DAY = date(2026, 8, 20)


def fresh(**kw) -> UserStats:
    s = UserStats(user_id="u", total_points=0, current_streak=0, longest_streak=0,
                  questions_answered=0, correct_answers=0, quizzes_completed=0,
                  repairs_used=0, best_milestone=0)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_first_day_starts_a_streak():
    s = fresh()
    c = touch_streak(s, DAY)
    assert c.extended and s.current_streak == 1 and not c.repaired


def test_consecutive_days_extend_it():
    s = fresh(last_active_date=DAY - timedelta(days=1), current_streak=4)
    c = touch_streak(s, DAY)
    assert c.extended and s.current_streak == 5 and not c.repaired


def test_practising_twice_in_a_day_does_not_double_count():
    s = fresh(last_active_date=DAY, current_streak=4)
    c = touch_streak(s, DAY)
    assert not c.extended and s.current_streak == 4


def test_one_missed_day_is_repaired_automatically():
    s = fresh(last_active_date=DAY - timedelta(days=2), current_streak=30)
    c = touch_streak(s, DAY)
    assert c.repaired is True
    assert s.current_streak == 31, "a repaired day continues the run rather than restarting it"
    assert c.repairs_left == scoring.MONTHLY_REPAIRS - 1


def test_repairs_run_out_after_the_monthly_allowance():
    s = fresh(last_active_date=DAY - timedelta(days=2), current_streak=10,
              repairs_month=DAY.strftime("%Y-%m"), repairs_used=scoring.MONTHLY_REPAIRS)
    c = touch_streak(s, DAY)
    assert c.repaired is False
    assert s.current_streak == 1, "with no repairs left the streak resets"


def test_repair_allowance_resets_each_month():
    august = fresh(last_active_date=date(2026, 8, 30), current_streak=10,
                   repairs_month="2026-08", repairs_used=scoring.MONTHLY_REPAIRS)
    c = touch_streak(august, date(2026, 9, 1))   # missed 31 Aug, arriving in a new month
    assert c.repaired is True and august.repairs_used == 1


def test_a_long_absence_is_not_repaired():
    s = fresh(last_active_date=DAY - timedelta(days=5), current_streak=40)
    c = touch_streak(s, DAY)
    assert c.repaired is False and s.current_streak == 1


@pytest.mark.parametrize("days,expected", [(2, None), (3, 3), (7, 7), (8, None), (30, 30), (365, 365)])
def test_milestones_fire_on_the_right_days(days, expected):
    s = fresh(last_active_date=DAY - timedelta(days=1), current_streak=days - 1,
              best_milestone=max([m for m in scoring.MILESTONES if m <= days - 1] + [0]))
    c = touch_streak(s, DAY)
    assert c.milestone == expected


def test_a_milestone_is_only_celebrated_once():
    s = fresh(last_active_date=DAY - timedelta(days=1), current_streak=6)
    first = touch_streak(s, DAY)
    assert first.milestone == 7
    second = touch_streak(s, DAY + timedelta(days=1))
    assert second.milestone is None


def test_milestones_award_points():
    s = fresh(last_active_date=DAY - timedelta(days=1), current_streak=6)
    before = s.total_points
    touch_streak(s, DAY)
    assert s.total_points == before + scoring.milestone_points(7)


def test_every_milestone_has_copy():
    for m in scoring.MILESTONES:
        title, body = scoring.MILESTONE_COPY[m]
        assert title and body


def test_milestone_copy_is_encouraging_not_coercive():
    joined = " ".join(t + " " + b for t, b in scoring.MILESTONE_COPY.values()).lower()
    for word in ("don't lose", "you'll lose", "disappointed", "shame", "failure"):
        assert word not in joined


# --- API ---------------------------------------------------------------------

def test_answer_reports_streak_fields(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 3}).json()
    r = client.post(f"/api/quiz/{s['id']}/answer",
                    json={"question_id": s["questions"][0]["id"], "selected_index": 0}).json()
    assert r["streak"] == 1 and r["streak_extended"] is True
    assert r["streak_repaired"] is False
    assert r["repairs_left"] == scoring.MONTHLY_REPAIRS


def test_stats_expose_repairs_and_next_milestone(client, user):
    s = client.post("/api/quiz/start", json={"mode": "mixed", "count": 3}).json()
    client.post(f"/api/quiz/{s['id']}/answer", json={"question_id": s["questions"][0]["id"], "selected_index": 0})
    st = client.get("/api/me/stats").json()
    assert st["repairs_left"] == scoring.MONTHLY_REPAIRS and st["repairs_used"] == 0
    assert st["next_milestone"] == 3 and st["best_milestone"] == 0
