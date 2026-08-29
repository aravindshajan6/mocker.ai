import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine
from .content import scheduler
from .routers import auth, current_affairs, quiz, stats, topics
from .seed import seed_demo_user, seed_questions

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight forward-only migrations for columns added after the first release.
        await conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS source_url VARCHAR(512)"))
    async with SessionLocal() as db:
        await seed_questions(db)
        await seed_demo_user(db)
    job = scheduler.start()
    yield
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
app.include_router(current_affairs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
