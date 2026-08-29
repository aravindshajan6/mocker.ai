"""Load topics and question banks from data/questions/*.json into the database (idempotent)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .auth import hash_password
from .models import Question, Topic, User, UserStats

log = logging.getLogger("seed")

TOPICS = [
    ("indian-history", "Indian History", "Ancient to modern India and the freedom struggle", "🏛️"),
    ("kerala", "Kerala", "History, renaissance, geography and culture of Kerala", "🌴"),
    ("indian-polity", "Constitution & Polity", "Constitution, parliament, judiciary and governance", "⚖️"),
    ("geography", "Geography", "India and the world — physical and political", "🗺️"),
    ("economy", "Economy", "Indian economy, banking and basic economics", "📈"),
    ("general-science", "General Science", "Physics, chemistry and biology basics", "🔬"),
    ("arts-culture", "Arts & Culture", "Dance, music, literature, awards and heritage", "🎭"),
    ("world-gk", "World GK", "Organisations, inventions, personalities and important days", "🌍"),
    ("sports", "Sports", "Games, trophies, records and famous athletes", "🏏"),
    ("computers-tech", "Computers & IT", "Basics of computers, internet and cyber laws", "💻"),
    ("environment", "Environment", "Ecology, biodiversity, climate and conservation", "🌿"),
    ("current-affairs", "Current Affairs", "Fresh questions generated from recent news", "📰"),
]


def fingerprint(text: str) -> str:
    norm = re.sub(r"\W+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()[:40]


async def seed_topics(db: AsyncSession) -> dict[str, int]:
    existing = {t.slug: t for t in (await db.execute(select(Topic))).scalars().all()}
    for i, (slug, name, desc, icon) in enumerate(TOPICS):
        t = existing.get(slug)
        if t is None:
            t = Topic(slug=slug, name=name, description=desc, icon=icon, sort_order=i)
            db.add(t)
            existing[slug] = t
        else:
            t.name, t.description, t.icon, t.sort_order = name, desc, icon, i
    await db.commit()
    return {t.slug: t.id for t in (await db.execute(select(Topic))).scalars().all()}


async def seed_questions(db: AsyncSession) -> int:
    topic_ids = await seed_topics(db)
    data_dir = Path(settings.data_dir)
    if not data_dir.exists():
        log.warning("data dir %s not found; skipping question seed", data_dir)
        return 0
    known = set((await db.execute(select(Question.fingerprint))).scalars().all())
    added = 0
    for path in sorted(data_dir.glob("*.json")):
        try:
            items = json.loads(path.read_text())
        except Exception as e:  # noqa: BLE001
            log.error("skipping %s: %s", path, e)
            continue
        for item in items:
            slug = item.get("topic") or path.stem
            tid = topic_ids.get(slug)
            if tid is None:
                continue
            opts = item.get("options") or []
            ans = item.get("answer")
            if len(opts) != 4 or not isinstance(ans, int) or not 0 <= ans < 4:
                continue
            fp = fingerprint(item["question"])
            if fp in known:
                continue
            known.add(fp)
            db.add(Question(
                topic_id=tid, text=item["question"].strip(), options=[str(o).strip() for o in opts], correct_index=ans,
                explanation=(item.get("explanation") or "").strip(), difficulty=int(item.get("difficulty") or 1),
                tags=item.get("tags") or [], source=item.get("source") or "seed", fingerprint=fp,
                published_at=date.fromisoformat(item["published_at"]) if item.get("published_at") else None,
                source_url=item.get("source_url"), source_ref=item.get("source_ref"),
            ))
            added += 1
        await db.commit()
    log.info("seeded %d new questions", added)
    return added


async def seed_demo_user(db: AsyncSession) -> None:
    """Create the demo account if configured and missing (idempotent)."""
    if not settings.demo_password:
        return
    email = settings.demo_email.lower()
    exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists:
        return
    user = User(email=email, name=settings.demo_name, password_hash=hash_password(settings.demo_password))
    user.stats = UserStats()
    db.add(user)
    await db.commit()
    log.info("created demo account %s", email)
