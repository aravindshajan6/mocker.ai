"""Pure-function tests for points, levels and badges — no database needed."""
from app.services import scoring


def test_points_scale_with_difficulty():
    assert scoring.points_for(True, 1, 1) == 10
    assert scoring.points_for(True, 2, 1) == 15
    assert scoring.points_for(True, 3, 1) == 20
    assert scoring.points_for(False, 3, 1) == 0


def test_combo_bonuses_kick_in_at_three_and_five():
    assert scoring.points_for(True, 1, 2) == 10
    assert scoring.points_for(True, 1, 3) == 15
    assert scoring.points_for(True, 1, 5) == 20


def test_levels_progress_and_cap():
    level, title, progress, to_next = scoring.level_for(0)
    assert (level, title, to_next) == (1, "Beginner", 100)
    assert progress == 0.0
    level, title, _, _ = scoring.level_for(350)
    assert (level, title) == (3, "Scholar")
    level, title, progress, _ = scoring.level_for(999_999)
    assert title == "Legend" and progress == 1.0


def test_badges_are_earned_not_given():
    none = scoring.badges_for(total_points=0, streak=0, longest_streak=0, answered=0, correct=0,
                              quizzes=0, perfect_quizzes=0)
    assert none == []
    many = scoring.badges_for(total_points=1200, streak=7, longest_streak=7, answered=120, correct=100,
                              quizzes=12, perfect_quizzes=1)
    assert {"first-quiz", "ten-quizzes", "perfect-score", "streak-3", "streak-7",
            "hundred-questions", "sharp-shooter", "thousand-points"} <= set(many)
    assert "streak-30" not in many


def test_every_badge_has_display_metadata():
    all_badges = scoring.badges_for(total_points=10**6, streak=99, longest_streak=99, answered=10**4,
                                    correct=10**4, quizzes=999, perfect_quizzes=9)
    assert set(all_badges) <= set(scoring.BADGE_META)
