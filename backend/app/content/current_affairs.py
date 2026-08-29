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
from datetime import date, datetime, timedelta, timezone
from time import mktime

import feedparser
import httpx
from sqlalchemy import select
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
    r"stock market|sensex today|nifty today|gold rate|petrol price|weather today)\b",
    re.I,
)

SYSTEM_PROMPT = """You write multiple-choice questions for Kerala PSC aspirants (Degree Level and 10th Level
Common Preliminary Examination). Current-affairs questions in these papers test durable, examinable facts
drawn from the news: who was appointed, which state/country/organisation, which scheme or award, which
number or date, which place.

RULES
1. Work only from the supplied news items. Never rely on facts not present in the item.
2. Produce at most one question per item, only where the item contains a clear, verifiable fact of the
   kind above. Skip items about crime, accidents, opinion, speculation or minor local matters by setting
   usable=false. It is fine to skip most items.
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


def generate_with_llm(items: list[dict], target: int, batch_size: int = 10) -> list[dict]:
    """Ask the configured LLM for MCQs, batch by batch, until `target` questions are collected."""
    cfg = llm.current_config()
    out: list[dict] = []
    for start in range(0, len(items), batch_size):
        if len(out) >= target:
            break
        batch = items[start:start + batch_size]
        lines = [f"[{i}] ({it['published']}, {it['source']}) {it['title']}\n{it['summary'][:900]}"
                 for i, it in enumerate(batch)]
        user = "News items:\n\n" + "\n\n".join(lines) + f"\n\nAllowed topic slugs: {', '.join(TOPIC_SLUGS)}."
        try:
            data = llm.complete_json(SYSTEM_PROMPT, user, schema=OUTPUT_SCHEMA, cfg=cfg)
        except llm.LLMError as e:
            log.warning("LLM batch at %d failed: %s", start, e)
            if "rate limited" in str(e) or "HTTP 401" in str(e) or "HTTP 403" in str(e) or "no API key" in str(e):
                break  # no point retrying the remaining batches
            continue
        for q in data.get("questions", []) if isinstance(data, dict) else []:
            idx = q.get("source_index", -1) if isinstance(q, dict) else -1
            src = batch[idx] if isinstance(idx, int) and 0 <= idx < len(batch) else None
            v = _validate(q, src)
            if v:
                out.append(v)
    return out[:target]


async def run_daily(db: AsyncSession, *, day: date | None = None, force: bool = False,
                    target: int | None = None) -> ContentRun:
    """Fetch news, generate questions and insert them for `day` (default: today, IST).

    Idempotent per day unless force=True: a second call on the same day is recorded as 'skipped'.
    Blocking network/LLM work runs in a thread so the event loop stays responsive.
    """
    day = day or today()
    target = target or settings.current_affairs_target
    if not force:
        prior = (await db.execute(select(ContentRun).where(ContentRun.day == day, ContentRun.status == "ok"))).scalars().first()
        if prior:
            run = ContentRun(day=day, status="skipped", message="already generated today", finished_at=utcnow())
            db.add(run)
            await db.commit()
            return run

    cfg = llm.current_config()
    run = ContentRun(day=day, provider=cfg.provider if cfg.available else "heuristic", model=cfg.model if cfg.available else "")
    db.add(run)
    await db.commit()
    try:
        items = await asyncio.to_thread(fetch_items, settings.current_affairs_days_back, 80)
        run.fetched = len(items)
        questions: list[dict] = []
        if cfg.available:
            questions = await asyncio.to_thread(generate_with_llm, items, target)
        if not questions:
            questions = generate_heuristic(items, max_questions=target)
            run.provider = "heuristic" if not cfg.available else f"{cfg.provider}->heuristic"
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
        run.status = "ok"
        run.message = f"{inserted} questions added for {day.isoformat()}"
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
