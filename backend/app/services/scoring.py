"""Points, levels and badges — kept pure so they are easy to test and tweak."""
from __future__ import annotations

from ..config import settings

DIFFICULTY_BONUS = {1: 0, 2: 5, 3: 10}

LEVELS: list[tuple[int, str]] = [
    (0, "Beginner"),
    (100, "Learner"),
    (300, "Scholar"),
    (700, "Achiever"),
    (1500, "Expert"),
    (3000, "Master"),
    (6000, "Champion"),
    (12000, "Legend"),
]


def points_for(is_correct: bool, difficulty: int, combo: int) -> int:
    """combo = number of consecutive correct answers *including* this one."""
    if not is_correct:
        return 0
    pts = settings.base_points + DIFFICULTY_BONUS.get(difficulty, 0)
    if combo >= 3:
        pts += 5  # on fire
    if combo >= 5:
        pts += 5  # unstoppable
    return pts


def level_for(points: int) -> tuple[int, str, float, int]:
    """Returns (level_number, title, progress 0..1 within level, points_to_next)."""
    level = 1
    title = LEVELS[0][1]
    floor = 0
    ceiling = LEVELS[1][0]
    for i, (threshold, name) in enumerate(LEVELS):
        if points >= threshold:
            level, title, floor = i + 1, name, threshold
            ceiling = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else threshold * 2
    span = max(ceiling - floor, 1)
    progress = min((points - floor) / span, 1.0)
    return level, title, progress, max(ceiling - points, 0)


def badges_for(*, total_points: int, streak: int, longest_streak: int, answered: int,
               correct: int, quizzes: int, perfect_quizzes: int) -> list[str]:
    b: list[str] = []
    if quizzes >= 1:
        b.append("first-quiz")
    if quizzes >= 10:
        b.append("ten-quizzes")
    if quizzes >= 50:
        b.append("fifty-quizzes")
    if perfect_quizzes >= 1:
        b.append("perfect-score")
    if longest_streak >= 3:
        b.append("streak-3")
    if longest_streak >= 7:
        b.append("streak-7")
    if longest_streak >= 30:
        b.append("streak-30")
    if answered >= 100:
        b.append("hundred-questions")
    if answered >= 500:
        b.append("five-hundred-questions")
    if answered >= 50 and correct / max(answered, 1) >= 0.8:
        b.append("sharp-shooter")
    if total_points >= 1000:
        b.append("thousand-points")
    return b


BADGE_META = {
    "first-quiz": ("First Step", "Completed your first quiz", "🌱"),
    "ten-quizzes": ("Regular", "Completed 10 quizzes", "📚"),
    "fifty-quizzes": ("Dedicated", "Completed 50 quizzes", "🏛️"),
    "perfect-score": ("Flawless", "Scored 100% in a quiz", "💯"),
    "streak-3": ("Warming Up", "3-day streak", "🔥"),
    "streak-7": ("On Fire", "7-day streak", "🔥🔥"),
    "streak-30": ("Unstoppable", "30-day streak", "🌟"),
    "hundred-questions": ("Century", "Answered 100 questions", "💪"),
    "five-hundred-questions": ("Marathoner", "Answered 500 questions", "🏃"),
    "sharp-shooter": ("Sharp Shooter", "80%+ accuracy over 50 questions", "🎯"),
    "thousand-points": ("Point Collector", "Earned 1,000 points", "💎"),
}


# --- Exam mode -------------------------------------------------------------
# Kerala PSC objective papers: 1 mark per correct answer, 1/3 deducted per wrong answer,
# nothing deducted for a blank. Source: the instruction block printed on the question booklet.
NEGATIVE_MARK = 1.0 / 3.0


def exam_raw_score(correct: int, wrong: int, penalty: float = NEGATIVE_MARK) -> float:
    """Marks as the Commission would compute them."""
    return round(correct - wrong * penalty, 4)


def exam_points(correct: int, wrong: int, total: int) -> int:
    """App points for an exam attempt — mirrors the real penalty so the incentive matches."""
    return max(0, round(correct * 10 - wrong * 10 * NEGATIVE_MARK))


def guess_break_even(options: int = 4, penalty: float = NEGATIVE_MARK) -> float:
    """Expected marks from a blind guess. At 4 options and a 1/3 penalty this is exactly 0,
    which is the single most useful fact about negative marking: eliminating even one option
    makes guessing profitable, while guessing with no information is a coin flip on your score."""
    return round((1 / options) - (1 - 1 / options) * penalty, 4)
