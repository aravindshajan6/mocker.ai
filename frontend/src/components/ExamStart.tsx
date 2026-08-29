"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Timer } from "lucide-react";
import Mascot from "@/components/Mascot";
import { ErrorNote, Item, PageHeader, SkeletonPage, Stagger } from "@/components/ui";
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

  if (loading) return <SkeletonPage />;

  return (
    <Stagger className="pt-1 pb-6 flex flex-col gap-4">
      <Item>
        <PageHeader title="Exam mode" icon={<Timer size={20} />}
          subtitle="A timed paper in the real format — no feedback until you submit."
          action={<Mascot mood="think" size={64} />} />
      </Item>

      {running && (
        <Item>
          <div className="card p-4 border-accent/50" style={{ background: "var(--accent-soft)" }}>
            <p className="font-extrabold">You have a paper in progress</p>
            <p className="text-sm font-semibold text-muted mt-0.5">
              {Math.floor(running.seconds_remaining / 60)} minutes left of your {running.total}-question exam.
            </p>
            <button className="btn btn-primary w-full mt-3" onClick={() => router.push(`/exam/${running.id}`)}>
              Resume the paper
            </button>
          </div>
        </Item>
      )}

      <Item>
        <div className="card p-4">
          <h2 className="font-extrabold">How it is scored</h2>
          <ul className="text-sm font-semibold text-muted mt-2 space-y-1.5">
            <li>✓ <b className="text-ink">+1 mark</b> for each correct answer</li>
            <li>✕ <b className="text-ink">−1/3 mark</b> for each wrong answer</li>
            <li>○ <b className="text-ink">Nothing</b> for a question left blank</li>
          </ul>
          <p className="text-xs font-semibold text-muted mt-3 leading-relaxed">
            With four options, a blind guess averages exactly <b className="text-ink">0 marks</b> — it neither helps
            nor hurts. The moment you can rule out one option, guessing is worth it. That judgement is what this
            mode trains.
          </p>
        </div>
      </Item>

      <ErrorNote message={error} />

      <div className="flex flex-col gap-3">
        {PRESETS.map((p) => (
          <Item key={p.count}>
            <button className="card card-interactive p-4 w-full text-left disabled:opacity-60 flex items-center gap-4"
              onClick={() => start(p.count, p.minutes)} disabled={starting !== null || !!running}>
              <div className="grid place-items-center h-11 w-11 rounded-2xl bg-info-soft text-info shrink-0 font-extrabold text-sm">
                {p.count}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-extrabold">{p.label}</div>
                <div className="text-xs text-muted font-semibold mt-0.5">
                  {p.count} questions · {p.minutes} minutes · {p.hint}
                </div>
              </div>
              <span className="text-sm font-extrabold text-primary shrink-0">
                {starting === p.count ? "Starting…" : "Start →"}
              </span>
            </button>
          </Item>
        ))}
      </div>

      {running && (
        <p className="text-xs text-muted font-semibold text-center">
          Finish or submit your current paper before starting a new one.
        </p>
      )}
    </Stagger>
  );
}
