"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import { ProgressBar, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { HistoryRow, LeaderboardRow, Stats } from "@/lib/types";

const DAY = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

export default function Progress() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.stats(), api.history(), api.leaderboard()])
      .then(([s, h, b]) => { setStats(s); setHistory(h); setBoard(b); })
      .catch((e) => setError(e?.message || "Something went wrong. Please try again."));
  }, []);

  if (error) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
  if (!stats) return <Spinner label="Counting your points…" />;

  const maxAnswered = Math.max(1, ...stats.last_7_days.map((d) => d.answered));
  const allBadges = Object.entries(stats.badge_meta);

  return (
    <div className="pt-4 flex flex-col gap-5 pop-in">
      <section className="flex items-center gap-3">
        <Mascot mood={stats.current_streak > 0 ? "happy" : "idle"} size={80} />
        <div>
          <h1 className="text-2xl font-extrabold">Your progress</h1>
          <p className="text-muted font-semibold text-sm">Level {stats.level} · {stats.level_title}</p>
        </div>
      </section>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Points" value={stats.total_points.toLocaleString()} tone="text-primary" />
        <Stat label="Day streak" value={`🔥 ${stats.current_streak}`} sub={`best ${stats.longest_streak}`} />
        <Stat label="Accuracy" value={`${Math.round(stats.accuracy * 100)}%`} sub={`${stats.correct_answers}/${stats.questions_answered}`} />
        <Stat label="Quizzes" value={String(stats.quizzes_completed)} />
      </section>

      <section className="card p-4">
        <div className="flex justify-between text-xs font-extrabold text-muted mb-2">
          <span>Level {stats.level} · {stats.level_title}</span>
          <span>{stats.points_to_next_level} pts to next</span>
        </div>
        <ProgressBar value={stats.level_progress} color="var(--accent)" />
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold mb-3">Last 7 days</h2>
        <div className="grid grid-cols-7 gap-2 items-end h-28">
          {stats.last_7_days.map((d) => {
            const date = new Date(d.day + "T00:00:00");
            const h = d.answered ? Math.max(12, (d.answered / maxAnswered) * 100) : 6;
            return (
              <div key={d.day} className="flex flex-col items-center justify-end h-full gap-1">
                <span className="text-[10px] font-extrabold text-muted">{d.answered || ""}</span>
                <div className="w-full rounded-lg transition-all" style={{ height: `${h}%`, background: d.answered ? "var(--primary)" : "var(--line)" }} title={`${d.answered} answered, ${d.points} pts`} />
                <span className="text-[11px] font-extrabold text-muted">{DAY[date.getDay()]}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold mb-3">Badges</h2>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {allBadges.map(([key, [name, desc, icon]]) => {
            const got = stats.badges.includes(key);
            return (
              <div key={key} title={desc} className={`rounded-2xl p-3 text-center ${got ? "bg-accent-soft" : "bg-surface-2 opacity-50"}`}>
                <div className="text-2xl">{got ? icon : "🔒"}</div>
                <div className="text-xs font-extrabold mt-1 leading-tight">{name}</div>
                <div className="text-[10px] text-muted font-semibold mt-0.5 leading-tight">{desc}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold mb-3">This week&apos;s leaderboard</h2>
        {board.length === 0 ? <p className="text-sm text-muted font-semibold">No activity yet this week.</p> : (
          <ol className="flex flex-col gap-1.5">
            {board.map((r, i) => (
              <li key={i} className={`flex items-center gap-3 rounded-xl px-3 py-2 ${r.is_me ? "bg-primary-soft" : ""}`}>
                <span className="w-6 text-sm font-extrabold text-muted">{i + 1}</span>
                <span className="flex-1 font-bold truncate">{r.name}{r.is_me ? " (you)" : ""}</span>
                <span className="font-extrabold tabular-nums">{r.points} pts</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold mb-3">Recent quizzes</h2>
        {history.length === 0 ? (
          <p className="text-sm text-muted font-semibold">Nothing yet — <Link href="/" className="text-primary font-extrabold">start your first quiz</Link>.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {history.map((h) => (
              <li key={h.id} className="py-2.5 flex items-center gap-3">
                <span className="text-xl">{h.topic_icon ?? (h.mode === "daily" ? "📅" : "🎯")}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-bold truncate">{h.topic ?? (h.mode === "daily" ? "Daily challenge" : "Mixed practice")}</p>
                  <p className="text-xs text-muted font-semibold">{h.finished_at ? new Date(h.finished_at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : ""} · {h.correct}/{h.total} correct</p>
                </div>
                <Link href={`/quiz/${h.id}/result`} className="text-sm font-extrabold text-primary">+{h.score}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, sub, tone = "" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="card p-3">
      <div className={`text-xl font-extrabold ${tone}`}>{value}</div>
      <div className="text-[11px] font-extrabold text-muted uppercase tracking-wide">{label}</div>
      {sub && <div className="text-[11px] font-semibold text-muted">{sub}</div>}
    </div>
  );
}
