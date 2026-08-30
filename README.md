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

### Accounts

Public sign-up is **closed** (`ALLOW_SIGNUP=false`): accounts are provisioned by an administrator in
the app, or seeded from `.env` on startup. Three are created by default — change these before hosting:

| Account | Default password | Role |
| --- | --- | --- |
| `admin@mocker.app` | `changeme-admin` | administrator |
| `aswathi@gmail.com` | `aswathi123` | learner |
| `demo@mocker.app` | `demo1234` | learner |

### Admin

Administrators get an **Admin** section (hidden from everyone else, and enforced server-side on every
endpoint) covering: triggering the news fetch and the answer-key audit on demand; adding, editing and
retiring questions; provisioning accounts and resetting passwords; and managing LLM provider keys.

Keys are tried in priority order. A key the provider rejects is switched off automatically and a
rate-limited one rests for six hours while the next takes over — so when a free tier runs out you add
another key in the UI and generation carries on without a redeploy. Keys are stored server-side and
only ever displayed masked.

Legacy note: a demo account is created on startup: **demo@mocker.app / demo1234** (change or disable via `DEMO_EMAIL` / `DEMO_PASSWORD` in `.env`).

Stop with `docker compose down` (add `-v` to wipe the database).

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router, TypeScript), Tailwind v4, Motion (transitions), anime.js v4 (mascot), lucide-react, canvas-confetti |
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
frontend/src/app        /login /register / /daily /current-affairs /practice /practice/[slug] /review
                        /exam /exam/[id] /exam/[id]/result /quiz/[id] /quiz/[id]/result /history
                        /progress /settings /offline
frontend/src/components AppShell + nav/ (sidebar, mobile drawer), AppData (shared fetch), ui.tsx (design kit),
                        Mascot.tsx (SVG + anime.js), Quiz.tsx, Exam.tsx, PwaProvider.tsx
data/questions/         question banks (JSON) — see data/QUESTION_SCHEMA.md
data/importers/         dataset importers (MILU)
data/validate.py        validator for question files
```

## Content

* `data/questions/<topic>.json` — hand-authored, fact-checked banks (~1,150 questions across 11 topics).
* `data/questions/milu-*.json` — imported from [MILU](https://huggingface.co/datasets/murthyrudra/milu-cleaned)
  (CC-BY-4.0, arXiv:2411.02538) after strict filtering. Re-run with `data/importers/milu.py`.
* **Previous-year questions (PYQs)** — real Kerala PSC questions with the official answer key, imported from
  papers published on keralapsc.gov.in. Every one carries its provenance ("Asked in Kerala PSC 079/2026 · Q37")
  and links to the source PDF. Options are reproduced verbatim, never reshuffled, because accurate reproduction
  is a condition of the KPSC reuse licence — so `pyq-*.json` files are exempt from the answer-position balance
  check in `data/validate.py`. Re-run with `data/importers/pyq.py`.
* Current affairs — generated daily.** A scheduler inside the backend runs every morning at 06:00 IST
  (`CURRENT_AFFAIRS_HOUR_IST`), fetches Indian news from RSS (Deccan Herald, The Hindu incl. Kerala, Onmanorama,
  Mathrubhumi, TOI), turns it into exam-style MCQs and inserts them straight into the database — no restart.
  * Generator: the LLM configured in `.env` (`LLM_PROVIDER` = `groq` (free) | `gemini` | `openrouter` |
    `ollama` | `anthropic`, with `LLM_API_KEY`), falling back to a dependency-free gazetteer generator
    (fill-in-the-blank on states/districts/organisations/numbers) when no key is set or the provider fails.
  * In the app: a "Today's news quiz" card with a 7-day strip, up to 3 fresh news questions mixed into the daily
    challenge, a *Current Affairs* practice topic (newest first) and "Read the news source" links.
  * Run it by hand: `docker compose exec backend python -m app.content.current_affairs --force`, or with
    `ADMIN_TOKEN` set: `curl -X POST "http://localhost:3001/api/admin/current-affairs/run?wait=true&force=true" -H "X-Admin-Token: $ADMIN_TOKEN"`.
    `GET /api/current-affairs` shows the last run's status.

* **Automated answer-key audit.** Imported (MILU) questions are the least trustworthy content in the
  bank — a sample review found roughly 1 in 20 had a wrong or ambiguous key. A nightly job (03:00 IST)
  asks the LLM to audit a slice of them: a confident "wrong answer" deactivates the question, an
  uncertain verdict flags it for a human, and everything else is marked checked so it is not re-paid for.
  It never rewrites a question or changes a key. Hand-authored and exam-paper questions are never audited —
  they carry their own provenance. Status: `GET /api/admin/verification`; run now:
  `POST /api/admin/verification/run?limit=50&wait=true` (needs `ADMIN_TOKEN`).

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

## Themes

Light, dark, and match-your-device, chosen in Settings or from the compact toggle in the sidebar. The
choice is applied before the first paint, so there is no flash of the wrong palette on load.

## Tests

```bash
docker compose exec backend python -m pytest tests -q     # API + scoring tests
cd frontend && npx tsc --noEmit && npx eslint src         # type + lint checks
python3 data/validate.py data/questions/*.json            # question bank validation
```

## Attribution

Previous-year questions are reproduced from official papers published by the
[Kerala Public Service Commission](https://www.keralapsc.gov.in), whose
[copyright policy](https://www.keralapsc.gov.in/copyright) permits reproduction with acknowledgement.
Imported dataset questions come from [MILU](https://huggingface.co/datasets/murthyrudra/milu-cleaned) (CC-BY-4.0).
Mocker is an independent study tool, not affiliated with or endorsed by the KPSC.
