from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stats: Mapped[UserStats] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserStats(Base):
    __tablename__ = "user_stats"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    quizzes_completed: Mapped[int] = mapped_column(Integer, default=0)
    # Streak repairs: a missed day is forgiven a couple of times a month so one bad day does not
    # end a long run (and with it, usually, the habit).
    repairs_month: Mapped[str | None] = mapped_column(String(7), nullable=True)   # "2026-08"
    repairs_used: Mapped[int] = mapped_column(Integer, default=0)
    last_repair_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    best_milestone: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="stats")


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(255), default="")
    icon: Mapped[str] = mapped_column(String(16), default="📘")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(64), default="seed")
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # for current affairs
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)  # e.g. "Kerala PSC 079/2026 · Q37"
    explanation_long: Mapped[str | None] = mapped_column(Text, nullable=True)   # cached "explain more" text
    # Automated answer-key audit (see content/verify.py)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)      # ok | wrong_answer | ambiguous
    verdict_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(16))  # daily | topic | mixed
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    daily_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    question_ids: Mapped[list] = mapped_column(JSON)
    # Exam mode only: server-authoritative deadline so a client clock can't buy extra time.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    negative_marking: Mapped[float] = mapped_column(Float, default=0.0)
    raw_score: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    bonus: Mapped[int] = mapped_column(Integer, default=0)

    attempts: Mapped[list[Attempt]] = relationship(back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_sessions_user_daily", "user_id", "daily_date"),)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("quiz_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    selected_index: Mapped[int] = mapped_column(Integer)  # -1 = deliberately left blank (exam mode)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[QuizSession] = relationship(back_populates="attempts")

    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_attempt_session_question"),)


class AppConfig(Base):
    """Small key/value store for server-generated secrets (currently the VAPID keypair)."""
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class UserPrefs(Base):
    __tablename__ = "user_prefs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Local wall-clock time the learner picked, plus the zone it means. Stored apart so a user who
    # travels keeps "19:00 my time" rather than drifting.
    reminder_hour: Mapped[int] = mapped_column(Integer, default=19)
    reminder_minute: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    telegram_code_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminded_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    failures: Mapped[int] = mapped_column(Integer, default=0)


class ReviewCard(Base):
    """FSRS scheduling state for one (user, question) pair — see services/srs.py."""
    __tablename__ = "review_cards"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON)          # fsrs Card.to_dict()
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_review_due", "user_id", "due_at"),)


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    question_ids: Mapped[list] = mapped_column(JSON)


class ContentRun(Base):
    """One execution of the current-affairs generator (for status display and idempotency)."""
    __tablename__ = "content_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    generated: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | ok | error | skipped
    message: Mapped[str] = mapped_column(Text, default="")
