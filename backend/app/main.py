import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine
from .content import scheduler
from .routers import auth, current_affairs, exam, prefs, quiz, stats, topics
from .seed import seed_demo_user, seed_questions

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight forward-only migrations for columns added after the first release.
        await conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS source_url VARCHAR(512)"))
        await conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS source_ref VARCHAR(160)"))
        for ddl in (
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS duration_seconds INTEGER",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS negative_marking DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS raw_score DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE attempts ADD COLUMN IF NOT EXISTS marked_for_review BOOLEAN DEFAULT FALSE",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS explanation_long TEXT",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS verdict VARCHAR(16)",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS verdict_confidence DOUBLE PRECISION",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS verdict_note TEXT",
        ):
            await conn.execute(text(ddl))
    async with SessionLocal() as db:
        await seed_questions(db)
        await seed_demo_user(db)
    jobs = scheduler.start()
    yield
    for job in jobs:
        job.cancel()
    await engine.dispose()


app = FastAPI(title="Mocker API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(quiz.router)
app.include_router(stats.router)
app.include_router(exam.router)
app.include_router(prefs.router)
app.include_router(current_affairs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
