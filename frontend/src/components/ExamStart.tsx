"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { ExamState } from "@/lib/types";

const PRESETS = [
  { label: "Full paper", count: 100, minutes: 75, hint: "Kerala PSC prelims format" },
  { label: "Half paper", count: 50, minutes: 38, hint: "Same pace, half the time" },
  { label: "Quick mock", count: 25, minutes: 19, hint: "A short pressure test" },
];

export default function ExamStart() {
  const router = useRouter();
  const [running, setRunning] = useState<ExamState | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.currentExam().then(setRunning).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const start = async (count: number, minutes: number) => {
    setStarting(count);
    setError(null);
    try {
      const s = await api.startExam({ count, duration_minutes: minutes });
      router.push(`/exam/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Could not start the exam.");
      setStarting(null);
    }
  };

  if (loading) return <Spinner label="Checking for an exam in progress…" />;

  return (
    <div className="pt-4 pb-10 flex flex-col gap-5 pop-in">
      <section className="flex items-center gap-3">
        <Mascot mood="think" size={88} />
        <div>
          <h1 className="text-2xl font-extrabold leading-tight">Exam mode</h1>
          <p className="text-muted font-semibold text-sm mt-0.5">A timed paper in the real format — no feedback until you submit.</p>
        </div>
      </section>

      {running && (
        <section className="card p-4 border-accent/50" style={{ background: "var(--accent-soft)" }}>
          <p className="font-extrabold">You have a paper in progress</p>
          <p className="text-sm font-semibold text-muted mt-0.5">
            {Math.floor(running.seconds_remaining / 60)} minutes left of your {running.total}-question exam.
          </p>
          <button className="btn btn-primary w-full mt-3" onClick={() => router.push(`/exam/${running.id}`)}>Resume the paper</button>
        </section>
      )}

      <section className="card p-4">
        <h2 className="font-extrabold">How it is scored</h2>
        <ul className="text-sm font-semibold text-muted mt-2 space-y-1.5">
          <li>✓ <b className="text-ink">+1 mark</b> for each correct answer</li>
          <li>✕ <b className="text-ink">−1/3 mark</b> for each wrong answer</li>
          <li>○ <b className="text-ink">Nothing</b> for a question left blank</li>
        </ul>
        <p className="text-xs font-semibold text-muted mt-3 leading-relaxed">
          With four options, a blind guess averages exactly <b className="text-ink">0 marks</b> — it neither helps nor
          hurts. The moment you can rule out one option, guessing is worth it. That judgement is what this mode trains.
        </p>
      </section>

      <ErrorNote message={error} />

      <section className="flex flex-col gap-3">
        {PRESETS.map((p) => (
          <button key={p.count} className="card p-4 text-left transition hover:-translate-y-0.5 disabled:opacity-60 flex items-center gap-4"
            onClick={() => start(p.count, p.minutes)} disabled={starting !== null || !!running}>
            <div className="flex-1">
              <div className="font-extrabold">{p.label}</div>
              <div className="text-xs text-muted font-semibold mt-0.5">{p.count} questions · {p.minutes} minutes · {p.hint}</div>
            </div>
            <span className="text-sm font-extrabold text-primary">{starting === p.count ? "Starting…" : "Start →"}</span>
          </button>
        ))}
      </section>
      {running && <p className="text-xs text-muted font-semibold text-center">Finish or submit your current paper before starting a new one.</p>}
    </div>
  );
}
