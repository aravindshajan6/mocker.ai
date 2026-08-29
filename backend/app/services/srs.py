"""Spaced repetition using FSRS.

Why FSRS rather than SM-2: FSRS models memory as difficulty/stability/retrievability and, on the
open-source benchmark over hundreds of millions of reviews, reaches the same retention with roughly
20-30% fewer reviews than SM-2. The library ships sensible default parameters, so no per-user
training pipeline is needed.

A card here is one (user, question) pair. Every answer in the app rates that card, so review
scheduling is a by-product of ordinary practice — the user never has to "do their reviews" unless
they want to.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

# Default parameters; desired retention 0.9 is the library default and a sane target for exam prep.
_scheduler = Scheduler()

# Answering quickly and correctly is evidence of stronger recall than a slow correct answer.
FAST_MS = 6_000
SLOW_MS = 25_000


def rate(is_correct: bool, elapsed_ms: int | None) -> Rating:
    """Turn a multiple-choice outcome into an FSRS rating.

    A wrong answer is always Again. For correct answers we use response time as a weak proxy for
    confidence: fast means Easy, slow means Hard, anything in between is Good.
    """
    if not is_correct:
        return Rating.Again
    if elapsed_ms is None:
        return Rating.Good
    if elapsed_ms <= FAST_MS:
        return Rating.Easy
    if elapsed_ms >= SLOW_MS:
        return Rating.Hard
    return Rating.Good


def new_card() -> dict:
    return Card().to_dict()


def review(card_state: dict | None, is_correct: bool, elapsed_ms: int | None = None) -> tuple[dict, datetime, bool]:
    """Apply one review. Returns (new card state, next due time, was_lapse)."""
    card = Card.from_dict(card_state) if card_state else Card()
    was_review_state = card.last_review is not None
    updated, _log = _scheduler.review_card(card, rate(is_correct, elapsed_ms))
    lapsed = was_review_state and not is_correct
    return updated.to_dict(), updated.due, lapsed


def retrievability(card_state: dict) -> float:
    """Estimated probability the user still remembers this, right now (0-1)."""
    try:
        return float(_scheduler.get_card_retrievability(Card.from_dict(card_state)))
    except Exception:  # noqa: BLE001 - never let a scheduling detail break answering a question
        return 0.0


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
