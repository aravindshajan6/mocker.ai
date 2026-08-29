from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str


class TopicOut(BaseModel):
    slug: str
    name: str
    description: str
    icon: str
    question_count: int
    answered: int = 0
    accuracy: float | None = None


class QuestionOut(BaseModel):
    id: int
    text: str
    options: list[str]
    difficulty: int
    topic: str
    topic_icon: str
    published_at: date | None = None
    source_ref: str | None = None


class StartQuizIn(BaseModel):
    mode: str = Field(pattern="^(daily|topic|mixed|current-affairs|review)$")
    topic: str | None = None
    count: int | None = Field(default=None, ge=3, le=30)
    day: date | None = None  # current-affairs mode: which day's set (default today)


class StartExamIn(BaseModel):
    """Kerala PSC prelims by default: 100 questions, 75 minutes, 1/3 negative marking."""
    count: int = Field(default=100, ge=10, le=200)
    duration_minutes: int = Field(default=75, ge=5, le=240)
    topic: str | None = None  # optional: a single-topic mock


class SaveAnswerIn(BaseModel):
    question_id: int
    selected_index: int = Field(ge=-1, le=3)  # -1 = leave blank
    marked_for_review: bool = False


class ExamStateOut(BaseModel):
    id: str
    questions: list[QuestionOut]
    answers: dict[int, int]              # question_id -> selected index (-1 = blank)
    marked: list[int]
    seconds_remaining: int
    duration_seconds: int
    total: int
    submitted: bool


class ExamQuestionReview(BaseModel):
    question_id: int
    number: int
    text: str
    options: list[str]
    selected_index: int | None
    correct_index: int
    is_correct: bool
    skipped: bool
    explanation: str
    topic: str
    source_ref: str | None


class ExamResultOut(BaseModel):
    id: str
    total: int
    attempted: int
    correct: int
    wrong: int
    blank: int
    raw_score: float
    marks_lost_to_negative: float
    accuracy: float
    percentage: float
    points: int
    time_taken_seconds: int
    per_topic: list[dict]
    guess_break_even: float
    coaching: str
    review: list[ExamQuestionReview]


class AttemptState(BaseModel):
    question_id: int
    selected_index: int
    is_correct: bool
    correct_index: int
    explanation: str
    points: int
    source_url: str | None = None
    source_ref: str | None = None


class SessionOut(BaseModel):
    id: str
    mode: str
    topic: str | None
    questions: list[QuestionOut]
    attempts: list[AttemptState]
    score: int
    correct: int
    finished: bool


class AnswerIn(BaseModel):
    question_id: int
    selected_index: int = Field(ge=0, le=3)
    elapsed_ms: int | None = Field(default=None, ge=0, le=3_600_000)  # informs review scheduling


class AnswerOut(BaseModel):
    is_correct: bool
    correct_index: int
    explanation: str
    source_url: str | None = None
    source_ref: str | None = None
    points: int
    combo: int
    score: int
    correct: int
    answered: int
    total: int
    streak: int
    streak_extended: bool


class FinishOut(BaseModel):
    score: int
    bonus: int
    correct: int
    total: int
    accuracy: float
    total_points: int
    level: int
    level_title: str
    points_to_next_level: int
    streak: int
    already_finished: bool
    new_badges: list[str]


class DayActivity(BaseModel):
    day: date
    answered: int
    correct: int
    points: int


class StatsOut(BaseModel):
    total_points: int
    level: int
    level_title: str
    level_progress: float
    points_to_next_level: int
    current_streak: int
    longest_streak: int
    questions_answered: int
    correct_answers: int
    accuracy: float
    quizzes_completed: int
    last_7_days: list[DayActivity]
    daily_done_today: bool
    daily_score_today: int | None
    badges: list[str]
    badge_meta: dict[str, list[str]]


class DailyOut(BaseModel):
    day: date
    size: int
    done: bool
    session_id: str | None
    score: int | None
    correct: int | None


class LeaderboardRow(BaseModel):
    name: str
    points: int
    is_me: bool


class HistoryRow(BaseModel):
    id: str
    mode: str
    topic: str | None
    topic_icon: str | None
    finished_at: datetime | None
    score: int
    correct: int
    total: int


class ActiveSessionOut(BaseModel):
    id: str
    mode: str
    topic: str | None
    topic_icon: str | None
    answered: int
    total: int


class CADay(BaseModel):
    day: date
    count: int
    answered: int          # how many of that day's questions this user has answered
    session_id: str | None # this user's session for that day, if any
    finished: bool
    score: int | None


class CARun(BaseModel):
    day: date
    status: str
    provider: str
    model: str
    fetched: int
    generated: int
    inserted: int
    message: str
    finished_at: datetime | None


class CurrentAffairsOut(BaseModel):
    today: date
    days: list[CADay]      # last 7 days, newest first
    enabled: bool
    provider: str
    has_key: bool
    last_run: CARun | None


class ReviewDueOut(BaseModel):
    due_now: int
    due_today: int
    learning: int          # questions seen at least once and being scheduled
    next_due_at: datetime | None
    retention: float | None  # share of due reviews answered correctly, last 30 days
