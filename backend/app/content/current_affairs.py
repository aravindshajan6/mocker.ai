"""Current-affairs question generator.

Pulls recent Indian news from RSS feeds and turns it into exam-style MCQs, inserted straight into
the questions table (topic "current-affairs", published_at = run day). The scheduler in
app.content.scheduler calls run_daily() every morning; it can also be triggered via
POST /api/admin/current-affairs/run or from the CLI:

    python -m app.content.current_affairs            # run now (uses configured LLM, or heuristics)
    python -m app.content.current_affairs --dry-run  # only show the headlines that would be used

Generation path: configured LLM provider (see content/llm.py) -> heuristic gazetteer fallback.
Feeds were verified on 2026-08-29. PIB has no working English RSS feed and Wikinews shut down in
May 2026, so mainstream Indian outlets are used. Only facts are extracted; summaries are never
republished verbatim.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from time import mktime

import feedparser
import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import ContentRun, Question, Topic, utcnow
from ..seed import fingerprint
from ..services.quiz import today
from . import llm
from .heuristic import generate_heuristic

log = logging.getLogger("current-affairs")

FEEDS: list[tuple[str, str]] = [
    # (name, url)  — full-text feeds first (better questions), then summary feeds
    ("Deccan Herald India", "https://www.deccanherald.com/api/v1/collections/india.rss"),
    ("Deccan Herald Science", "https://www.deccanherald.com/api/v1/collections/science.rss"),
    ("Deccan Herald Business", "https://www.deccanherald.com/api/v1/collections/business.rss"),
    ("Deccan Herald Sports", "https://www.deccanherald.com/api/v1/collections/sports.rss"),
    ("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("The Hindu Kerala", "https://www.thehindu.com/news/national/kerala/feeder/default.rss"),
    ("The Hindu Sci-Tech", "https://www.thehindu.com/sci-tech/feeder/default.rss"),
    ("Onmanorama Kerala", "https://www.onmanorama.com/kerala.feeds.onmrss.xml"),
    ("Mathrubhumi English", "https://english.mathrubhumi.com/rss"),
    ("TOI Top Stories", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
]

TOPIC_SLUGS = [
    "indian-history", "kerala", "indian-polity", "geography", "economy", "general-science",
    "arts-culture", "world-gk", "sports", "computers-tech", "environment",
]

# Headlines that rarely yield durable, examinable facts.
SKIP_PATTERNS = re.compile(
    r"\b(live updates?|watch:|opinion|editorial|horoscope|box office|review:|explained|memoir|booked|FIR|"
    r"dies at|dead|death|killed|murder|rape|accident|crash|arrested|held for|stabbed|suicide|assault|injured|"
    r"threatens|explode|end life|tested positive|rescued|saves|narrow escape|missing|drown|molest|"
    r"stock market|sensex today|nifty today|gold rate|petrol price|weather today|"
    r"wrestlemania|wwe|bollywood|celebrity|actor|actress|movie|film|netflix|trailer|reality show|dating)\b",
    re.I,
)

SYSTEM_PROMPT = """You write multiple-choice questions for Kerala PSC aspirants (Degree Level and 10th Level
Common Preliminary Examination). Current-affairs questions in these papers test durable, examinable facts
drawn from the news: who was appointed, which state/country/organisation, which scheme or award, which
number or date, which place.

RULES
1. Work only from the supplied news items. Never rely on facts not present in the item.
2. Produce at most one question per item, only where the item contains a clear, verifiable fact of the
   kind above. Skip items about crime, accidents, opinion, speculation, entertainment/celebrity/wrestling
   gossip, or minor local matters by setting usable=false. It is fine to skip most items.
3. The question must stand alone: include enough context (month/year, event, body) so it can be answered
   without seeing the article. Do not test headline wording.
4. Exactly 4 options, exactly one correct. Distractors must be the same entity type and comparable
   specificity (if the answer is an Indian state, all options are Indian states). Never use
   "All of the above", "None of the above", "Both A and B" or joke options.
5. The stem must not contain the answer string. Options must not be orderable by length.
6. explanation: one or two sentences, <= 240 characters, adds a supporting fact from the item.
7. topic: the substantive GK topic slug the fact belongs to (e.g. an ISRO launch -> general-science,
   a Kerala appointment -> kerala, an RBI decision -> economy, a sports result -> sports).
8. difficulty: 1 for one-step recall, 2 for two facts, 3 for numeric/multi-fact reasoning.
9. Write in clear, neutral exam English.

Respond with ONLY a JSON object of this exact shape:
{"questions": [{"source_index": 0, "usable": true, "question": "...", "options": ["...","...","...","..."],
  "answer": 0, "explanation": "...", "topic": "<slug>", "difficulty": 1}]}
Include one entry per news item (usable=false entries may leave the other fields empty)."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_index": {"type": "integer"},
                    "usable": {"type": "boolean"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "topic": {"type": "string"},
                    "difficulty": {"type": "integer"},
                },
                "required": ["source_index", "usable"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;|&rsquo;|&lsquo;", "'", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_items(days: int = 2, max_items: int = 60) -> list[dict]:
    """Fetch recent, de-duplicated news items from the feed list."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "MockerQuizBot/0.1 (study app; polite RSS reader)"}
    with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
        for name, url in FEEDS:
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as e:  # noqa: BLE001
                log.warning("feed %s failed: %s", name, e)
                continue
            parsed = feedparser.parse(resp.content)
            for e in parsed.entries:
                title = _clean(getattr(e, "title", ""))
                if not title or SKIP_PATTERNS.search(title):
                    continue
                key = re.sub(r"\W+", " ", title.lower()).strip()[:80]
                if key in seen:
                    continue
                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    t = getattr(e, attr, None)
                    if t:
                        published = datetime.fromtimestamp(mktime(t), tz=timezone.utc)
                        break
                if published and published < cutoff:
                    continue
                body = ""
                if getattr(e, "content", None):
                    body = _clean(e.content[0].get("value", ""))
                if not body:
                    body = _clean(getattr(e, "summary", "") or getattr(e, "description", ""))
                seen.add(key)
                items.append({
                    "source": name, "title": title, "summary": body[:1500], "link": getattr(e, "link", ""),
                    "published": (published or datetime.now(timezone.utc)).date().isoformat(),
                })
    # Longer bodies yield better questions: full-text feeds first.
    items.sort(key=lambda i: len(i["summary"]), reverse=True)
    return items[:max_items]


def _validate(q: dict, src: dict | None) -> dict | None:
    """Normalise one LLM-produced question into our bank schema, or None if it fails the gates."""
    if not q.get("usable"):
        return None
    opts = [str(o).strip() for o in (q.get("options") or [])]
    stem = str(q.get("question") or "").strip()
    ans = q.get("answer")
    if len(opts) != 4 or len(set(o.lower() for o in opts)) != 4 or not stem or not isinstance(ans, int):
        return None
    if not 0 <= ans < 4 or any(len(o) > 90 or not o for o in opts):
        return None
    if any(re.search(r"(all|none) of the above|\bboth\b", o, re.I) for o in opts):
        return None
    if opts[ans].lower() in stem.lower():
        return None
    if not 8 <= len(stem.split()) <= 45:
        return None
    topic = q.get("topic") if q.get("topic") in TOPIC_SLUGS else "world-gk"
    diff = q.get("difficulty") if q.get("difficulty") in (1, 2, 3) else 1
    # LLMs tend to park the right answer in the same slot; shuffle so position carries no signal.
    order = list(range(4))
    random.shuffle(order)
    opts = [opts[i] for i in order]
    ans = order.index(ans)
    return {
        "topic": "current-affairs",
        "question": stem,
        "options": opts,
        "answer": ans,
        "explanation": str(q.get("explanation") or "").strip()[:300],
        "difficulty": diff,
        "tags": ["current-affairs", topic],
        "source": "news",
        "published_at": src["published"] if src else None,
        "source_url": src["link"] if src else None,
    }


async def generate_with_llm(db, items: list[dict], target: int, batch_size: int = 6, max_retries: int = 3) -> list[dict]:
    """Ask the configured LLM for MCQs, batch by batch, until `target` questions are collected.

    Free tiers are tight on tokens-per-minute (Groq: 8k TPM), so batches are small and a 429 triggers a
    wait-and-retry instead of giving up — the daily job is not latency sensitive.
    """
    import asyncio

    from ..services import llm_keys

    out: list[dict] = []
    for start in range(0, len(items), batch_size):
        if len(out) >= target:
            break
        batch = items[start:start + batch_size]
        lines = [f"[{i}] ({it['published']}, {it['source']}) {it['title']}\n{it['summary'][:600]}"
                 for i, it in enumerate(batch)]
        user = "News items:\n\n" + "\n\n".join(lines) + f"\n\nAllowed topic slugs: {', '.join(TOPIC_SLUGS)}."
        data = None
        for attempt in range(max_retries + 1):
            try:
                # Failover across stored keys, so one exhausted free tier does not stop the day.
                data, _used = await llm_keys.complete_json_failover(db, SYSTEM_PROMPT, user, max_tokens=3000)
                break
            except llm.LLMError as e:
                msg = str(e)
                if "HTTP 401" in msg or "HTTP 403" in msg or "no API key" in msg:
                    log.warning("LLM auth problem, aborting: %s", msg)
                    return out
                if "rate limited" in msg and attempt < max_retries:
                    wait = 65 if "per minute" in msg or "TPM" in msg or "RPM" in msg else 20 * (attempt + 1)
                    log.info("rate limited; waiting %ds before retrying batch at %d", wait, start)
                    await asyncio.sleep(wait)
                    continue
                log.warning("LLM batch at %d failed: %s", start, msg)
                break
        if data is None:
            continue
        # Gentle pacing between batches keeps us under per-minute token caps.
        await asyncio.sleep(3)
        for q in data.get("questions", []) if isinstance(data, dict) else []:
            idx = q.get("source_index", -1) if isinstance(q, dict) else -1
            src = batch[idx] if isinstance(idx, int) and 0 <= idx < len(batch) else None
            v = _validate(q, src)
            if v:
                out.append(v)
    return out[:target]


async def run_daily(db: AsyncSession, *, day: date | None = None, force: bool = False,
                    target: int | None = None, trigger: str = "manual") -> ContentRun:
    """Fetch news, generate questions and insert them for `day` (default: today, IST).

    Idempotent per day unless force=True: a second call on the same day is recorded as 'skipped'.
    Blocking network/LLM work runs in a thread so the event loop stays responsive.
    """
    day = day or today()
    target = target or settings.current_affairs_target
    if not force:
        # Judged on questions, not on a prior 'ok': a run can finish successfully having inserted
        # nothing, and that day still needs another go.
        health = await day_health(db, day)
        if health.healthy:
            run = ContentRun(day=day, status="skipped", trigger=trigger,
                             message=f"{health.questions} questions already published for {day}",
                             finished_at=utcnow())
            db.add(run)
            await db.commit()
            return run
        attempt = health.attempts + 1
    else:
        attempt = 1

    from ..services import llm_keys
    chain = await llm_keys.configs(db)
    can_generate = bool(chain)
    run = ContentRun(day=day, provider=chain[0].provider if can_generate else "heuristic",
                     model=chain[0].model if can_generate else "", attempt=attempt, trigger=trigger)
    db.add(run)
    await db.commit()
    try:
        items = await asyncio.to_thread(fetch_items, settings.current_affairs_days_back, 80)
        run.fetched = len(items)
        questions: list[dict] = []
        if can_generate:
            questions = await generate_with_llm(db, items, target)
        if not questions:
            questions = generate_heuristic(items, max_questions=target)
            run.provider = "heuristic" if not can_generate else f"{run.provider}->heuristic"
        run.generated = len(questions)
        random.shuffle(questions)  # insertion order must not leak the answer-position pattern

        topic_id = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one()
        known = set((await db.execute(select(Question.fingerprint))).scalars().all())
        inserted = 0
        for q in questions:
            fp = fingerprint(q["question"])
            if fp in known:
                continue
            known.add(fp)
            db.add(Question(
                topic_id=topic_id, text=q["question"], options=q["options"], correct_index=q["answer"],
                explanation=q["explanation"], difficulty=q["difficulty"], tags=q["tags"], source=q["source"],
                fingerprint=fp, published_at=day, source_url=q.get("source_url"),
            ))
            inserted += 1
        run.inserted = inserted
        if inserted and any(q["source"] == "news" for q in questions):
            # LLM questions supersede the shallower heuristic ones for the same day.
            await db.execute(update(Question).where(Question.topic_id == topic_id, Question.published_at == day,
                                                    Question.source == "news-heuristic").values(is_active=False))
        total_for_day = (await db.execute(
            select(func.count()).select_from(Question)
            .where(Question.topic_id == topic_id, Question.published_at == day, Question.is_active.is_(True))
        )).scalar_one()
        if total_for_day >= settings.current_affairs_min_questions:
            run.status = "ok"
            run.message = f"{inserted} added; {total_for_day} questions now published for {day.isoformat()}"
        else:
            # Nothing usable came back. Recorded as an error so the supervisor schedules a retry
            # rather than treating the day as finished.
            run.status = "error"
            run.message = (f"only {total_for_day} question(s) for {day.isoformat()} "
                           f"(fetched {run.fetched}, generated {run.generated}, added {inserted})")
    except Exception as e:  # noqa: BLE001
        log.exception("current-affairs run failed")
        run.status = "error"
        run.message = f"{type(e).__name__}: {e}"[:500]
    run.finished_at = utcnow()
    await db.commit()
    log.info("current-affairs run %s: %s", run.status, run.message)
    return run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="fetch and print headlines only")
    ap.add_argument("--force", action="store_true", help="generate even if today's run already succeeded")
    ap.add_argument("--target", type=int, default=None)
    ap.add_argument("--max-items", type=int, default=20)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.dry_run:
        items = fetch_items(days=settings.current_affairs_days_back, max_items=args.max_items)
        cfg = llm.current_config()
        print(f"provider={cfg.provider} model={cfg.model} key={'yes' if cfg.available else 'no'}")
        for it in items:
            print(f"- [{it['published']}] {it['source']}: {it['title']}  ({len(it['summary'])} chars)")
        return 0

    async def _go():
        from ..db import SessionLocal
        async with SessionLocal() as db:
            run = await run_daily(db, force=args.force, target=args.target)
            print(f"{run.status}: {run.message} (provider={run.provider}, fetched={run.fetched}, generated={run.generated})")
            return 0 if run.status in ("ok", "skipped") else 1

    return asyncio.run(_go())


if __name__ == "__main__":
    sys.exit(main())


# --- health and retry -------------------------------------------------------
# Retry delays after each failed attempt of the day. Front-loaded, because most failures are a
# transient feed timeout or a rate-limited key that clears in minutes, then spread out so a genuine
# outage does not hammer the provider all day.
RETRY_BACKOFF_MINUTES = (10, 20, 45, 120, 240)


@dataclass
class DayHealth:
    day: date
    questions: int
    healthy: bool
    attempts: int
    last_status: str | None
    last_message: str
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    exhausted: bool          # out of retries and still not healthy


async def day_health(db: AsyncSession, day: date | None = None, now: datetime | None = None) -> DayHealth:
    """Did the day's pull actually work?

    Judged on the questions that exist for that day, not on whether a run reported success: a run
    can finish 'ok' having inserted nothing (every item filtered out, or every generated question a
    duplicate), and that day is just as empty as one that crashed.
    """
    day = day or today()
    now = now or datetime.now(timezone.utc)
    ca = (await db.execute(select(Topic.id).where(Topic.slug == "current-affairs"))).scalar_one_or_none()
    questions = 0
    if ca is not None:
        questions = (await db.execute(
            select(func.count()).select_from(Question)
            .where(Question.topic_id == ca, Question.published_at == day, Question.is_active.is_(True))
        )).scalar_one()

    runs = (await db.execute(
        select(ContentRun).where(ContentRun.day == day, ContentRun.status != "skipped")
        .order_by(ContentRun.started_at)
    )).scalars().all()
    real = [r for r in runs if r.status in ("ok", "error")]
    attempts = len(real)
    last = real[-1] if real else None
    healthy = questions >= settings.current_affairs_min_questions

    next_retry = None
    exhausted = False
    if not healthy and last and last.finished_at:
        if attempts > len(RETRY_BACKOFF_MINUTES) or attempts >= settings.current_affairs_max_attempts:
            exhausted = True
        else:
            delay = RETRY_BACKOFF_MINUTES[min(attempts - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
            next_retry = last.finished_at + timedelta(minutes=delay)

    return DayHealth(
        day=day, questions=questions, healthy=healthy, attempts=attempts,
        last_status=last.status if last else None, last_message=last.message if last else "",
        last_attempt_at=last.finished_at if last else None,
        next_retry_at=next_retry, exhausted=exhausted,
    )


async def should_run_now(db: AsyncSession, now_ist: datetime) -> tuple[bool, str]:
    """Decide whether the supervisor should start a run this tick, and say why."""
    if not settings.current_affairs_enabled:
        return False, "disabled"
    health = await day_health(db, now_ist.date())
    if health.healthy:
        return False, f"{health.questions} questions already published for {health.day}"
    if now_ist.hour < settings.current_affairs_hour_ist:
        return False, f"waiting for {settings.current_affairs_hour_ist:02d}:00 IST"
    if health.attempts == 0:
        return True, "first attempt of the day"
    if health.exhausted:
        return False, f"gave up after {health.attempts} attempts"
    if health.next_retry_at and datetime.now(timezone.utc) < health.next_retry_at:
        return False, f"retry {health.attempts + 1} due at {health.next_retry_at:%H:%M} UTC"
    return True, f"retry {health.attempts + 1} after a failed attempt"
