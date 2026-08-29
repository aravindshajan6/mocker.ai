"""Current-affairs question generator.

Pulls recent Indian news from RSS feeds and asks Claude to turn them into exam-style MCQs,
then writes them to data/questions/current-affairs.json (picked up by the seeder on restart).

Run inside the backend container:
    python -m app.content.current_affairs            # fetch + generate (needs ANTHROPIC_API_KEY)
    python -m app.content.current_affairs --dry-run  # only show the headlines that would be used

Feeds were verified on 2026-08-29. PIB has no working English RSS feed, and Wikinews was shut down
in May 2026, so mainstream Indian outlets are used instead. Only facts are extracted; summaries are
never republished verbatim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime

import feedparser
import httpx

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
    r"dies at|killed|murder|rape|accident|crash|arrested|held for|stabbed|suicide|assault|"
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
3. The question must stand alone: include enough context (year, event, body) so it can be answered
   without seeing the article. Do not test headline wording.
4. Exactly 4 options, exactly one correct. Distractors must be the same entity type and comparable
   specificity (if the answer is an Indian state, all options are Indian states). Never use
   "All of the above", "None of the above", "Both A and B" or joke options.
5. The stem must not contain the answer string. Options must not be orderable by length.
6. explanation: one or two sentences, <= 240 characters, adds a supporting fact from the item.
7. topic: the substantive GK topic slug the fact belongs to (e.g. an ISRO launch -> general-science,
   a Kerala appointment -> kerala, an RBI decision -> economy, a sports result -> sports).
8. difficulty: 1 for one-step recall, 2 for two facts, 3 for numeric/multi-fact reasoning.
9. Write in clear, neutral exam English."""

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
                    "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                    "answer": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                    "topic": {"type": "string", "enum": TOPIC_SLUGS},
                    "difficulty": {"type": "integer", "minimum": 1, "maximum": 3},
                },
                "required": ["source_index", "usable", "question", "options", "answer", "explanation", "topic", "difficulty"],
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
    headers = {"User-Agent": "MockerQuizBot/0.1 (+https://github.com/; study app; polite RSS reader)"}
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


def generate_with_claude(items: list[dict], model: str = "claude-opus-5", batch_size: int = 10) -> list[dict]:
    """Ask Claude to produce MCQs; returns validated question dicts in our bank schema."""
    import anthropic  # imported lazily so the app runs without the SDK configured

    client = anthropic.Anthropic()
    out: list[dict] = []
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        lines = []
        for i, it in enumerate(batch):
            lines.append(f"[{i}] ({it['published']}, {it['source']}) {it['title']}\n{it['summary'][:900]}")
        user = "News items:\n\n" + "\n\n".join(lines) + f"\n\nAllowed topic slugs: {', '.join(TOPIC_SLUGS)}."
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=8000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            )
        except anthropic.RateLimitError as e:
            log.warning("rate limited, stopping early: %s", e)
            break
        except anthropic.APIStatusError as e:
            log.error("API error %s: %s", e.status_code, e.message)
            continue
        if resp.stop_reason == "refusal":
            log.warning("batch refused (%s)", getattr(resp.stop_details, "category", None))
            continue
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.error("non-JSON response for batch at %d", start)
            continue
        for q in data.get("questions", []):
            if not q.get("usable"):
                continue
            src = batch[q["source_index"]] if 0 <= q.get("source_index", -1) < len(batch) else None
            opts = [str(o).strip() for o in q["options"]]
            if len(set(opts)) != 4 or any(re.search(r"(all|none) of the above|both", o, re.I) for o in opts):
                continue
            if opts[q["answer"]].lower() in q["question"].lower():
                continue
            out.append({
                "topic": "current-affairs",
                "question": q["question"].strip(),
                "options": opts,
                "answer": int(q["answer"]),
                "explanation": q["explanation"].strip(),
                "difficulty": int(q["difficulty"]),
                "tags": ["current-affairs", q["topic"]],
                "source": "news",
                "published_at": src["published"] if src else None,
                "source_url": src["link"] if src else None,
            })
    return out


def merge_into_bank(new: list[dict], path: Path, keep_days: int = 90) -> int:
    """Append new questions to the bank file, dropping duplicates and stale items."""
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).date().isoformat()
    kept = [q for q in existing if (q.get("published_at") or "9999") >= cutoff]
    fps = {hashlib.sha256(re.sub(r"\W+", " ", q["question"].lower()).strip().encode()).hexdigest() for q in kept}
    added = 0
    for q in new:
        fp = hashlib.sha256(re.sub(r"\W+", " ", q["question"].lower()).strip().encode()).hexdigest()
        if fp in fps:
            continue
        fps.add(fp)
        kept.append(q)
        added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=2))
    return added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=2, help="how many days back to look (default 2)")
    ap.add_argument("--max-items", type=int, default=60)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--dry-run", action="store_true", help="fetch and print headlines only")
    ap.add_argument("--out", default=None, help="output file (default: <DATA_DIR>/current-affairs.json)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    items = fetch_items(days=args.days, max_items=args.max_items)
    log.info("fetched %d candidate news items", len(items))
    if args.dry_run:
        for it in items:
            print(f"- [{it['published']}] {it['source']}: {it['title']}  ({len(it['summary'])} chars)")
        return 0

    from ..config import settings
    if not settings.anthropic_api_key:
        log.error("ANTHROPIC_API_KEY is not set; cannot generate questions. Use --dry-run to inspect feeds.")
        return 2
    questions = generate_with_claude(items, model=args.model)
    log.info("generated %d usable questions", len(questions))
    out = Path(args.out) if args.out else Path(settings.data_dir) / "current-affairs.json"
    added = merge_into_bank(questions, out)
    log.info("wrote %s (+%d new). Restart the backend to load them.", out, added)
    return 0


if __name__ == "__main__":
    sys.exit(main())
