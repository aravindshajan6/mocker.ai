"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Mascot, { type Mood } from "@/components/Mascot";
import { Chip, ProgressBar, Spinner } from "@/components/ui";
import { api, greeting } from "@/lib/api";
import type { ActiveSession, Daily, Stats, Topic, User } from "@/lib/types";

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
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.me(), api.stats(), api.daily(), api.topics(), api.active()])
      .then(([u, s, d, t, a]) => { setUser(u); setStats(s); setDaily(d); setTopics(t); setActive(a); })
      .catch((e) => setError(e.message));
  }, []);

  const start = async (mode: "daily" | "topic" | "mixed", topic?: string) => {
    setStarting(topic ?? mode);
    try {
      const s = await api.startQuiz({ mode, topic });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(null);
    }
  };

  if (error) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
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
