"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Mascot, { type Mood } from "@/components/Mascot";
import { Chip, ProgressBar, Spinner } from "@/components/ui";
import { api, greeting } from "@/lib/api";
import type { ActiveSession, CurrentAffairs, Daily, ReviewDue, Stats, Topic, User } from "@/lib/types";

const NUDGES = [
  "One quiz a day keeps the exam fear away.",
  "Small steps every day add up to big scores.",
  "You don't have to be perfect — just show up.",
  "Every question you answer is one less surprise on exam day.",
  "Consistency beats cramming. Let's do a few.",
];

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [daily, setDaily] = useState<Daily | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [active, setActive] = useState<ActiveSession[]>([]);
  const [ca, setCa] = useState<CurrentAffairs | null>(null);
  const [due, setDue] = useState<ReviewDue | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.me(), api.stats(), api.daily(), api.topics(), api.active(), api.currentAffairs(), api.reviewQueue()])
      .then(([u, s, d, t, a, c, r]) => { setUser(u); setStats(s); setDaily(d); setTopics(t); setActive(a); setCa(c); setDue(r); })
      .catch((e) => setError(e?.message || "Could not load your dashboard. Please try again."));
  }, []);

  const start = async (mode: "daily" | "topic" | "mixed" | "current-affairs" | "review", topic?: string, day?: string) => {
    setStarting(topic ?? day ?? mode);
    try {
      const s = await api.startQuiz({ mode, topic, day });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(null);
    }
  };

  if (error) return (
    <div className="mt-16 text-center flex flex-col items-center gap-3">
      <Mascot mood="oops" size={110} />
      <p className="text-danger font-bold">{error}</p>
      <button className="btn btn-ghost" onClick={() => location.reload()}>Try again</button>
    </div>
  );
  if (!user || !stats || !daily) return <Spinner label="Waking up Kunju…" />;

  const firstName = user.name.split(" ")[0];
  const mood: Mood = stats.daily_done_today ? "happy" : stats.current_streak === 0 && stats.questions_answered > 0 ? "sleepy" : "wave";
  const nudge = NUDGES[new Date().getDate() % NUDGES.length];
  const resumable = active.find((a) => a.mode !== "daily") ?? active[0];

  return (
    <div className="pt-4 flex flex-col gap-5 pop-in">
      {/* Greeting */}
      <section className="flex items-center gap-3">
        <Mascot mood={mood} size={96} />
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-extrabold leading-tight">{greeting()}, {firstName}!</h1>
          <p className="text-muted font-semibold text-sm mt-0.5">{stats.daily_done_today ? "Today’s challenge is done. Fancy a bit more?" : nudge}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            <Chip tone="accent">🔥 {stats.current_streak}-day streak</Chip>
            <Chip tone="primary">✨ {stats.total_points} pts · {stats.level_title}</Chip>
          </div>
        </div>
      </section>

      {/* Level */}
      <section className="card p-4">
        <div className="flex justify-between text-xs font-extrabold text-muted mb-2">
          <span>Level {stats.level} · {stats.level_title}</span>
          <span>{stats.points_to_next_level} pts to next level</span>
        </div>
        <ProgressBar value={stats.level_progress} color="var(--accent)" />
      </section>

      {/* Resume */}
      {resumable && (
        <section className="card p-4 flex items-center gap-3 border-primary/40">
          <span className="text-2xl">{resumable.topic_icon ?? "🎯"}</span>
          <div className="flex-1">
            <p className="font-extrabold">Continue where you left off</p>
            <p className="text-sm text-muted font-semibold">{resumable.topic ?? (resumable.mode === "daily" ? "Daily challenge" : "Quick practice")} · {resumable.answered}/{resumable.total} answered</p>
          </div>
          <Link href={`/quiz/${resumable.id}`} className="btn btn-ghost !min-h-10 px-4 text-sm">Resume</Link>
        </section>
      )}

      {/* Daily challenge */}
      <section className="card p-5 relative overflow-hidden" style={{ background: "linear-gradient(135deg, var(--primary-soft), var(--surface))" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wide text-primary">Today&apos;s challenge</p>
            <h2 className="text-xl font-extrabold mt-1">{daily.size} questions, all topics</h2>
            <p className="text-sm text-muted font-semibold mt-1">
              {daily.done ? `Done! You scored ${daily.score} pts (${daily.correct}/${daily.size} correct).` : "Same set for everyone today. Finish it to keep your streak alive and earn a +25 bonus."}
            </p>
          </div>
          <span className="text-3xl">📅</span>
        </div>
        <div className="mt-4 flex gap-2">
          {daily.done ? (
            <button className="btn btn-primary flex-1" onClick={() => start("mixed")} disabled={starting !== null}>
              {starting === "mixed" ? "Picking questions…" : "One more round →"}
            </button>
          ) : (
            <button className="btn btn-primary flex-1" onClick={() => start("daily")} disabled={starting !== null}>
              {starting === "daily" ? "Getting ready…" : daily.session_id ? "Continue today's challenge" : "Start today's challenge"}
            </button>
          )}
        </div>
      </section>

      {/* Spaced repetition */}
      {due && (due.due_now > 0 || due.due_today > 0) && (
        <ReviewCard due={due} starting={starting} onStart={() => start("review")} />
      )}

      {/* Exam mode */}
      <Link href="/exam" className="card p-4 flex items-center gap-3 transition hover:-translate-y-0.5">
        <span className="text-2xl">📝</span>
        <div className="flex-1">
          <p className="font-extrabold">Take a full mock exam</p>
          <p className="text-sm text-muted font-semibold">100 questions, 75 minutes, 1/3 negative marking — the real format.</p>
        </div>
        <span className="text-sm font-extrabold text-primary">→</span>
      </Link>

      {/* Current affairs */}
      {ca && <CurrentAffairsCard ca={ca} starting={starting} onStart={(day) => start("current-affairs", undefined, day)} />}

      {/* Topics */}
      <section>
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-lg font-extrabold">Practice by topic</h2>
          <button className="text-sm font-extrabold text-primary" onClick={() => start("mixed")} disabled={starting !== null}>Mixed quiz →</button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {topics.map((t) => {
            const pct = t.question_count ? t.answered / t.question_count : 0;
            return (
              <button key={t.slug} onClick={() => start("topic", t.slug)} disabled={starting !== null}
                className="card p-4 text-left transition hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-60 flex flex-col gap-2">
                <span className="text-2xl">{t.icon}</span>
                <span className="font-extrabold leading-tight">{t.name}</span>
                <span className="text-xs text-muted font-semibold">{starting === t.slug ? "Starting…" : `${t.answered}/${t.question_count} done${t.accuracy !== null ? ` · ${Math.round(t.accuracy * 100)}%` : ""}`}</span>
                <ProgressBar value={pct} className="!h-1.5" />
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}


function CurrentAffairsCard({ ca, starting, onStart }: { ca: CurrentAffairs; starting: string | null; onStart: (day: string) => void }) {
  const todayRow = ca.days[0];
  const hasToday = todayRow.count > 0;
  const fmt = (d: string) => new Date(d + "T00:00:00").toLocaleDateString(undefined, { weekday: "short" });
  const status = !hasToday
    ? ca.last_run?.status === "error"
      ? "Today\u2019s batch hit a snag \u2014 earlier days are still here."
      : "Fresh questions arrive every morning around 6am."
    : todayRow.finished
      ? `Done! ${todayRow.score} pts today.`
      : todayRow.answered > 0
        ? `${todayRow.answered}/${todayRow.count} answered \u2014 pick up where you left off.`
        : `${todayRow.count} new questions from today\u2019s news.`;
  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-wide text-accent">Current affairs</p>
          <h2 className="text-xl font-extrabold mt-1">{hasToday ? "Today\u2019s news quiz" : "Recent news quizzes"}</h2>
          <p className="text-sm text-muted font-semibold mt-1">{status}</p>
        </div>
        <span className="text-3xl">📰</span>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1.5">
        {[...ca.days].reverse().map((d) => {
          const isToday = d.day === ca.today;
          const empty = d.count === 0;
          const done = d.finished;
          return (
            <button key={d.day} disabled={empty || starting !== null} onClick={() => onStart(d.day)}
              title={empty ? "No questions" : `${d.count} questions${done ? " \u00b7 done" : d.answered ? ` \u00b7 ${d.answered} answered` : ""}`}
              className={`flex flex-col items-center rounded-xl py-2 text-[11px] font-extrabold transition disabled:opacity-40 ${done ? "bg-success-soft text-success" : d.answered ? "bg-primary-soft text-primary" : isToday && !empty ? "bg-accent-soft text-ink ring-2 ring-accent" : "bg-surface-2 text-muted"}`}>
              <span>{fmt(d.day)}</span>
              <span className="text-base leading-tight">{empty ? "\u00b7" : done ? "\u2713" : d.count}</span>
            </button>
          );
        })}
      </div>
      {hasToday && (
        <button className="btn btn-primary w-full mt-4" onClick={() => onStart(todayRow.day)} disabled={starting !== null || todayRow.finished}>
          {starting === todayRow.day ? "Loading\u2026" : todayRow.finished ? "Today\u2019s set completed" : todayRow.answered > 0 ? "Continue today\u2019s quiz" : "Start today\u2019s news quiz"}
        </button>
      )}
      {!ca.has_key && <p className="text-[11px] text-muted font-semibold mt-3">Running in basic mode \u2014 add an LLM key in .env for richer questions.</p>}
    </section>
  );
}


function ReviewCard({ due, starting, onStart }: { due: ReviewDue; starting: string | null; onStart: () => void }) {
  const ready = due.due_now > 0;
  return (
    <section className="card p-4 flex items-center gap-3" style={ready ? { background: "linear-gradient(135deg, var(--accent-soft), var(--surface))" } : undefined}>
      <span className="text-2xl">🔁</span>
      <div className="flex-1 min-w-0">
        <p className="font-extrabold">
          {ready
            ? `${due.due_now} question${due.due_now === 1 ? "" : "s"} ready to revise`
            : `${due.due_today} question${due.due_today === 1 ? "" : "s"} coming back later today`}
        </p>
        <p className="text-sm text-muted font-semibold">
          {ready
            ? "Timed to reach you just before you would have forgotten them."
            : "Spaced repetition is holding these until the moment they are worth repeating."}
          {due.retention !== null ? ` ${Math.round(due.retention * 100)}% retention so far.` : ""}
        </p>
      </div>
      {ready && (
        <button className="btn btn-ghost !min-h-10 px-4 text-sm shrink-0" onClick={onStart} disabled={starting !== null}>
          {starting === "review" ? "…" : "Revise"}
        </button>
      )}
    </section>
  );
}
