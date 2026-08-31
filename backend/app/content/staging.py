"""Phased classification of staged exam questions.

Parsing exam papers is free; deciding which of their questions are general knowledge costs LLM
tokens. There are thousands of parsed candidates and a free tier measured in tokens per day, so the
work is done in nightly instalments: each run classifies as many batches as the day's remaining
budget allows, then stops and picks up tomorrow.

Nothing is lost if a run is interrupted — every batch commits its own decisions, so a crash or a
rate limit costs at most one batch.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Question, StagedQuestion, Topic, utcnow
from ..seed import fingerprint
from ..services import budget, llm_keys
from . import llm

log = logging.getLogger("staging")

TOPIC_SLUGS = [
    "indian-history", "kerala", "indian-polity", "geography", "economy", "general-science",
    "arts-culture", "world-gk", "sports", "computers-tech", "environment", "english",
]
DROP = "drop"

# Measured over real runs: a batch of 20 costs about 2,240 tokens, i.e. ~80 per question once the
# system prompt is accounted for. Overestimating here is not "safe" — it makes the pacer idle when
# there is room to spare, and the per-minute ceiling is what actually limits throughput.
TOKENS_PER_QUESTION = 85
SYSTEM_PROMPT_TOKENS = 600

SYSTEM_PROMPT = f"""You are sorting questions taken from real Kerala PSC exam papers.

For each question decide the general-knowledge topic a Kerala PSC candidate would file it under, or
"{DROP}" if it is not general knowledge at all.

Valid topics: {", ".join(TOPIC_SLUGS)}.

"english" is for the General English section of ordinary PSC papers: grammar (tenses, voice,
reported speech, articles, prepositions, question tags, sentence correction) and vocabulary
(synonyms, antonyms, one-word substitutes, idioms, phrasal verbs, spelling).

Use "{DROP}" for:
  - mathematics, mental ability, reasoning, data interpretation
  - English comprehension passages; Malayalam grammar, vocabulary, comprehension or translation
  - literary criticism of specific poems, novels or authors (e.g. Mac Flecknoe, To His Coy Mistress,
    Tess of the D'Urbervilles, Preface to Lyrical Ballads) — these come from subject-specialist
    teacher papers and are NOT general knowledge
  - pedagogy, teaching methodology, educational psychology
  - post-specific technical content: surveying, mechanical/civil/electrical engineering, nursing,
    pharmacy, accountancy standards, law-exam detail, agriculture practice, tailoring, draughtsmanship
  - anything needing a diagram, table or passage that is not in the text

"arts-culture" is only for Indian art forms, dance, music, festivals, awards, heritage and Indian
literature in the general-knowledge sense (Jnanpith winners, famous Indian authors and works).

A question a candidate for a *general* post (LDC, LGS, Village Extension Officer, Police Constable,
Secretariat Assistant) would reasonably be expected to answer is general knowledge. When unsure
between a topic and "{DROP}", choose "{DROP}".

Respond with ONLY a JSON object:
{{"labels": [{{"i": 1, "topic": "kerala"}}, {{"i": 2, "topic": "{DROP}"}}]}}
One entry per question, using the number given."""


@dataclass
class StagingProgress:
    total: int
    pending: int
    kept: int
    dropped: int
    failed: int
    promoted: int          # kept rows that now exist in the question bank
    by_topic: dict[str, int]


async def progress(db: AsyncSession, batch: str = "pyq") -> StagingProgress:
    rows = dict((await db.execute(
        select(StagedQuestion.status, func.count()).where(StagedQuestion.batch == batch)
        .group_by(StagedQuestion.status)
    )).all())
    by_topic = dict((await db.execute(
        select(StagedQuestion.topic_slug, func.count())
        .where(StagedQuestion.batch == batch, StagedQuestion.status == "kept")
        .group_by(StagedQuestion.topic_slug)
    )).all())
    promoted = (await db.execute(
        select(func.count()).select_from(Question)
        .join(StagedQuestion, StagedQuestion.fingerprint == Question.fingerprint)
        .where(StagedQuestion.batch == batch)
    )).scalar_one()
    return StagingProgress(
        total=sum(rows.values()), pending=rows.get("pending", 0), kept=rows.get("kept", 0),
        dropped=rows.get("dropped", 0), failed=rows.get("failed", 0), promoted=promoted,
        by_topic={k: v for k, v in by_topic.items() if k},
    )


async def load_from_file(db: AsyncSession, path: Path, batch: str = "pyq") -> dict:
    """Load parsed-but-unclassified candidates produced by the importer's --stage step."""
    if not path.exists():
        return {"loaded": 0, "skipped": 0, "message": f"{path} not found"}
    known = set((await db.execute(select(StagedQuestion.fingerprint))).scalars().all())
    in_bank = set((await db.execute(select(Question.fingerprint))).scalars().all())
    loaded = skipped = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        fp = fingerprint(item["question"])
        if fp in known or fp in in_bank:
            skipped += 1
            continue
        known.add(fp)
        db.add(StagedQuestion(
            fingerprint=fp, batch=batch, text=item["question"], options=item["options"],
            correct_index=item["answer"], explanation=item.get("explanation", ""),
            difficulty=int(item.get("difficulty") or 2), tags=item.get("tags") or [],
            source=item.get("source") or "pyq", source_ref=item.get("source_ref"),
            source_url=item.get("source_url"),
            published_at=None if not item.get("published_at") else __import__("datetime").date.fromisoformat(item["published_at"]),
            exam_name=item.get("exam_name", "")[:200],
        ))
        loaded += 1
        if loaded % 500 == 0:
            await db.commit()
    await db.commit()
    return {"loaded": loaded, "skipped": skipped}


def _prompt(batch: list[StagedQuestion]) -> str:
    lines = []
    for n, q in enumerate(batch, start=1):
        opts = " | ".join(str(o)[:60] for o in q.options)
        exam = f" [from: {q.exam_name}]" if q.exam_name else ""
        lines.append(f"{n}. {q.text}{exam}\n   Options: {opts}")
    return "\n".join(lines)


async def classify_once(db: AsyncSession, *, max_questions: int | None = None,
                        batch_size: int = 20, batch: str = "pyq") -> dict:
    """Classify as many staged questions as today's remaining budget allows."""
    summary = {"considered": 0, "kept": 0, "dropped": 0, "failed": 0, "promoted": 0,
               "batches": 0, "stopped": "", "tokens": 0, "paused_seconds": 0.0}

    chain = await llm_keys.configs(db, settings.staging_model)
    if not chain:
        summary["stopped"] = "no LLM key configured"
        return summary
    cfg = chain[0]

    import time as _time
    deadline = _time.monotonic() + settings.staging_max_minutes * 60
    limit = max_questions or settings.staging_per_run
    pending = (await db.execute(
        select(StagedQuestion).where(StagedQuestion.batch == batch, StagedQuestion.status == "pending")
        .order_by(StagedQuestion.id).limit(limit)
    )).scalars().all()
    if not pending:
        summary["stopped"] = "nothing left to classify"
        return summary

    topic_ids = dict((await db.execute(select(Topic.slug, Topic.id))).all())
    pacer = budget.MinutePacer(cfg.provider)
    before = (await budget.status(db, cfg.provider, cfg.model)).used

    for start in range(0, len(pending), batch_size):
        if _time.monotonic() > deadline:
            summary["stopped"] = f"reached the {settings.staging_max_minutes}-minute run limit"
            break
        chunk = pending[start:start + batch_size]
        estimate = SYSTEM_PROMPT_TOKENS + len(chunk) * TOKENS_PER_QUESTION
        allowed, why = await budget.can_spend(db, cfg, estimate)
        if not allowed:
            summary["stopped"] = f"budget: {why}"
            break

        summary["paused_seconds"] += await pacer.wait_for(estimate)

        data = None
        for attempt in range(settings.staging_rate_limit_retries + 1):
            try:
                data, _used = await llm_keys.complete_json_failover(
                    db, SYSTEM_PROMPT, _prompt(chunk), max_tokens=1200,
                    model_override=settings.staging_model)
                break
            except llm.LLMError as e:
                msg = str(e)
                # A per-minute limit clears on its own; this job has all night, so wait rather
                # than abandoning the run with the daily allowance barely touched.
                if "rate limited" in msg and attempt < settings.staging_rate_limit_retries:
                    log.info("rate limited mid-run; waiting 65s (attempt %d)", attempt + 1)
                    await asyncio.sleep(65)
                    summary["paused_seconds"] += 65
                    continue
                log.warning("classification batch failed: %s", msg)
                summary["stopped"] = f"provider: {msg[:160]}"
                break
        if data is None:
            break
        after = (await budget.status(db, cfg.provider, cfg.model)).used
        pacer.record(max(0, after - before - summary["tokens"]) or estimate)
        summary["tokens"] = after - before

        labels = data.get("labels") if isinstance(data, dict) else None
        if not isinstance(labels, list):
            summary["stopped"] = "unusable response from the model"
            break

        decided: dict[int, str] = {}
        for entry in labels:
            if not isinstance(entry, dict):
                continue
            i, topic = entry.get("i"), entry.get("topic")
            if isinstance(i, int) and 1 <= i <= len(chunk) and isinstance(topic, str):
                decided[i] = topic.strip().lower()

        for n, q in enumerate(chunk, start=1):
            topic = decided.get(n)
            q.decided_at = utcnow()
            summary["considered"] += 1
            if topic in TOPIC_SLUGS:
                q.status, q.topic_slug = "kept", topic
                summary["kept"] += 1
            elif topic == DROP:
                q.status, q.note = "dropped", "not general knowledge"
                summary["dropped"] += 1
            else:
                # No usable label came back for this one; leave it pending for a later run.
                q.decided_at = None
                q.note = "no label returned"
                summary["failed"] += 1

        summary["promoted"] += await _promote(db, chunk, topic_ids)
        summary["batches"] += 1
        await db.commit()

    summary["paused_seconds"] = round(summary["paused_seconds"])
    summary["stopped"] = summary["stopped"] or "reached this run's limit"
    log.info("staging: %s", summary)
    return summary


async def _promote(db: AsyncSession, rows: list[StagedQuestion], topic_ids: dict[str, int]) -> int:
    """Move kept questions into the live bank."""
    promoted = 0
    for q in rows:
        if q.status != "kept" or not q.topic_slug:
            continue
        tid = topic_ids.get(q.topic_slug)
        if tid is None:
            continue
        exists = (await db.execute(select(Question.id).where(Question.fingerprint == q.fingerprint))).scalar()
        if exists:
            continue
        db.add(Question(
            topic_id=tid, text=q.text, options=q.options, correct_index=q.correct_index,
            explanation=q.explanation, difficulty=q.difficulty, tags=q.tags, source=q.source,
            fingerprint=q.fingerprint, source_ref=q.source_ref, source_url=q.source_url,
            published_at=q.published_at,
        ))
        promoted += 1
    return promoted
