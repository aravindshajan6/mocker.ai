# Mocker — daily GK practice for PSC exams

A calm, ad-free quiz app for Kerala PSC / SSC / UPSC-style General Knowledge practice.
Sign up, do today's 10-question challenge, practise by topic, keep a streak going. Kunju the elephant cheers you on.

## Run it

```bash
cp .env.example .env              # optional; defaults work for local use
(cd frontend && npm install)      # node_modules is vendored into the image (see note below)
docker compose up --build -d
# open http://localhost:3001
```

> The frontend Dockerfile copies `frontend/node_modules` from the host instead of running `npm ci` inside the
> build, because npm could not reach the registry reliably from inside Docker on the dev machine. If your Docker
> network is fine you can switch back to `RUN npm ci` in `frontend/Dockerfile`.

Only the frontend port (3001) is exposed. The browser talks to Next.js, which proxies `/api/*` to the FastAPI
backend inside the compose network; Postgres is reachable only from the backend.

A demo account is created on startup: **demo@mocker.app / demo1234** (change or disable via `DEMO_EMAIL` / `DEMO_PASSWORD` in `.env`).

Stop with `docker compose down` (add `-v` to wipe the database).

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router, TypeScript), Tailwind v4, anime.js v4 (mascot), canvas-confetti |
| Backend | FastAPI, SQLAlchemy 2 (async) + asyncpg, PyJWT (httpOnly cookie), bcrypt |
| Database | PostgreSQL 16 |
| Content | Hand-authored banks + MILU (AI4Bharat) import + optional current-affairs generator |

## Layout

```
backend/app/            FastAPI app
  routers/              auth, topics, quiz, stats
  services/scoring.py   points, levels, badges (pure functions)
  services/quiz.py      question selection, daily challenge, streak logic (IST day boundary)
  content/              current-affairs pipeline (RSS -> Claude -> MCQs)
  seed.py               loads data/questions/*.json on startup (idempotent, dedup by question text)
frontend/src/app        pages: /login /register / (home) /quiz/[id] /quiz/[id]/result /progress
frontend/src/components Mascot.tsx (SVG + anime.js), Quiz.tsx, Home.tsx, Result.tsx, Progress.tsx
data/questions/         question banks (JSON) — see data/QUESTION_SCHEMA.md
data/importers/         dataset importers (MILU)
data/validate.py        validator for question files
```

## Content

* `data/questions/<topic>.json` — hand-authored, fact-checked banks (~1,150 questions across 11 topics).
* `data/questions/milu-*.json` — imported from [MILU](https://huggingface.co/datasets/murthyrudra/milu-cleaned)
  (CC-BY-4.0, arXiv:2411.02538) after strict filtering. Re-run with `data/importers/milu.py`.
* Current affairs — `python -m app.content.current_affairs` inside the backend container pulls recent Indian news
  from RSS (PIB, The Hindu, ...) and, if `ANTHROPIC_API_KEY` is set, asks Claude to write exam-style MCQs
  which are written to `data/questions/current-affairs.json` and picked up on the next backend restart.

Add your own questions: drop a JSON file into `data/questions/` following the schema, run
`python3 data/validate.py data/questions/yourfile.json`, then `docker compose restart backend`.

## Scoring

* +10 per correct answer, +5 for medium, +10 for hard difficulty.
* Combo bonus: +5 from the 3rd consecutive correct answer, +5 more from the 5th.
* +25 for finishing the daily challenge, +20 for a perfect round (5+ questions).
* Streak counts consecutive IST days with at least one answered question.
* Levels: Beginner → Learner (100) → Scholar (300) → Achiever (700) → Expert (1,500) → Master (3,000) → Champion (6,000) → Legend (12,000).

## API (all under `/api`)

`POST auth/register|login|logout`, `GET auth/me`, `GET topics`, `GET quiz/daily`, `GET quiz/active`,
`POST quiz/start {mode: daily|topic|mixed, topic?, count?}`, `GET quiz/{id}`, `POST quiz/{id}/answer`,
`POST quiz/{id}/finish`, `POST quiz/{id}/abandon`, `GET me/stats`, `GET me/history`, `GET me/leaderboard`.
Interactive docs: `docker compose exec backend curl localhost:8000/docs` (not exposed on the host).
