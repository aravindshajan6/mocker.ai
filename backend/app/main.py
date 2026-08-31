import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from .config import settings
from .services.ratelimit import limiter, too_many_requests
from .db import Base, SessionLocal, engine
from .content import scheduler
from .routers import admin, auth, current_affairs, exam, prefs, quiz, stats, topics
from .seed import seed_accounts, seed_questions

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
            "ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS repairs_month VARCHAR(7)",
            "ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS repairs_used INTEGER DEFAULT 0",
            "ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS last_repair_on DATE",
            "ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS best_milestone INTEGER DEFAULT 0",
            "ALTER TABLE user_prefs ADD COLUMN IF NOT EXISTS telegram_code_issued_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
            "ALTER TABLE content_runs ADD COLUMN IF NOT EXISTS attempt INTEGER DEFAULT 1",
            "ALTER TABLE staged_questions ADD COLUMN IF NOT EXISTS exam_name VARCHAR(200) DEFAULT ''",
            "ALTER TABLE content_runs ADD COLUMN IF NOT EXISTS trigger VARCHAR(16) DEFAULT 'scheduled'",
            "ALTER TABLE questions ALTER COLUMN source TYPE VARCHAR(64)",
        ):
            await conn.execute(text(ddl))
    async with SessionLocal() as db:
        await seed_questions(db)
        await seed_accounts(db)
    jobs = scheduler.start()
    yield
    for job in jobs:
        job.cancel()
    await engine.dispose()


app = FastAPI(title="Mocker API", version="0.1.0", lifespan=lifespan)


# Next's `headers()` config does NOT apply to paths it serves via `rewrites()`, so /api/* reaches
# the browser with none of the frontend's security headers. Verified against the live response, not
# read off the config. The backend therefore sets its own; the two sets are kept consistent.
API_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    # An API response is never a document; forbid everything rather than mirror the app's CSP.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "Cache-Control": "no-store",
}


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    for k, v in API_SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if settings.hsts_enabled:
        # Only meaningful over https; enabled by config so a plain-http dev box does not send it.
        response.headers.setdefault("Strict-Transport-Security",
                                    "max-age=63072000; includeSubDomains")
    return response
# Rate limiting sits outermost so a flood is rejected before it reaches a database session.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, too_many_requests)
app.add_middleware(SlowAPIMiddleware)
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
app.include_router(admin.router)
app.include_router(current_affairs.router)


if settings.testing_hooks:
    # Only mounted when explicitly switched on, so a production image cannot expose it even by
    # accident. The test suite needs it because every test shares one source address.
    @app.post("/api/testing/reset-rate-limits")
    async def _reset_rate_limits():
        limiter.reset()
        return {"ok": True}


@app.get("/api/health")
async def health(response: Response):
    """Liveness AND readiness.

    A health check that only proves the process is listening is worse than none: the container
    reports healthy, Traefik routes to it, and every request 500s on a dead database. This touches
    Postgres, so an unhealthy container is one that genuinely cannot serve.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        response.status_code = 503
        return {"status": "degraded", "database": f"{type(e).__name__}"}
    return {"status": "ok", "database": "ok"}
