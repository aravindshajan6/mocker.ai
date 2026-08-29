"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import { ProgressBar, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { ExamResult as Result } from "@/lib/types";

function mmss(s: number) {
  const m = Math.floor(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m ${s % 60}s`;
}

export default function ExamResult({ id }: { id: string }) {
  const [r, setR] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"wrong" | "blank" | "all">("wrong");

  useEffect(() => {
    api.submitExam(id).then(setR).catch((e) => setError(e?.message || "Could not load your result."));
  }, [id]);

  if (error) return <div className="pt-10 text-center"><p className="text-danger font-bold">{error}</p><Link href="/exam" className="btn btn-ghost mt-4">Back</Link></div>;
  if (!r) return <Spinner label="Marking your paper…" />;

  const rows = r.review.filter((x) => filter === "all" || (filter === "wrong" ? !x.is_correct && !x.skipped : x.skipped));
  const good = r.percentage >= 50;

  return (
    <div className="pt-6 pb-10 flex flex-col gap-4 pop-in">
      <div className="text-center">
        <Mascot mood={good ? "celebrate" : "happy"} size={130} />
        <h1 className="text-2xl font-extrabold mt-1">{r.raw_score} / {r.total}</h1>
        <p className="text-muted font-semibold">marks after negative marking · {r.percentage}%</p>
      </div>

      <section className="card p-4 grid grid-cols-3 gap-3 text-center">
        <div><div className="text-xl font-extrabold text-success">{r.correct}</div><div className="text-[11px] font-extrabold text-muted">CORRECT</div></div>
        <div><div className="text-xl font-extrabold text-danger">{r.wrong}</div><div className="text-[11px] font-extrabold text-muted">WRONG</div></div>
        <div><div className="text-xl font-extrabold text-muted">{r.blank}</div><div className="text-[11px] font-extrabold text-muted">BLANK</div></div>
      </section>

      <section className="card p-4">
        <div className="flex justify-between text-sm font-bold"><span>Marks earned</span><span className="text-success">+{r.correct}</span></div>
        <div className="flex justify-between text-sm font-bold mt-1"><span>Lost to negative marking</span><span className="text-danger">−{r.marks_lost_to_negative}</span></div>
        <div className="flex justify-between text-base font-extrabold mt-2 pt-2 border-t border-line"><span>Final score</span><span>{r.raw_score}</span></div>
        <p className="text-xs font-semibold text-muted mt-3 leading-relaxed">{r.coaching}</p>
      </section>

      <section className="card p-4 grid grid-cols-3 gap-3 text-center">
        <div><div className="text-lg font-extrabold">{Math.round(r.accuracy * 100)}%</div><div className="text-[11px] font-extrabold text-muted">ACCURACY</div></div>
        <div><div className="text-lg font-extrabold">{mmss(r.time_taken_seconds)}</div><div className="text-[11px] font-extrabold text-muted">TIME TAKEN</div></div>
        <div><div className="text-lg font-extrabold text-primary">+{r.points}</div><div className="text-[11px] font-extrabold text-muted">POINTS</div></div>
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold mb-3">By topic</h2>
        <div className="flex flex-col gap-2.5">
          {r.per_topic.map((t) => (
            <div key={t.topic}>
              <div className="flex justify-between text-xs font-extrabold">
                <span>{t.icon} {t.topic}</span>
                <span className="text-muted">{t.correct}/{t.total}</span>
              </div>
              <ProgressBar value={t.total ? t.correct / t.total : 0} className="!h-1.5 mt-1"
                color={t.correct / Math.max(t.total, 1) >= 0.5 ? "var(--success)" : "var(--danger)"} />
            </div>
          ))}
        </div>
      </section>

      <section className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-extrabold">Review</h2>
          <div className="flex gap-1">
            {(["wrong", "blank", "all"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`text-xs font-extrabold px-2.5 py-1 rounded-lg ${filter === f ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted"}`}>
                {f === "wrong" ? `Wrong (${r.wrong})` : f === "blank" ? `Blank (${r.blank})` : `All (${r.total})`}
              </button>
            ))}
          </div>
        </div>
        {rows.length === 0 ? <p className="text-sm font-semibold text-muted">Nothing here — well done.</p> : (
          <div className="flex flex-col gap-3">
            {rows.slice(0, 60).map((x) => (
              <div key={x.question_id} className="border-t border-line pt-3 first:border-0 first:pt-0">
                <p className="text-[11px] font-extrabold text-muted">Q{x.number} · {x.topic}{x.source_ref ? ` · ${x.source_ref}` : ""}</p>
                <p className="font-bold mt-0.5 leading-snug">{x.text}</p>
                {x.skipped
                  ? <p className="text-sm font-bold text-muted mt-1">You left this blank</p>
                  : <p className="text-sm font-bold text-danger mt-1">Your answer: {x.options[x.selected_index!]}</p>}
                <p className="text-sm font-bold text-success">Correct: {x.options[x.correct_index]}</p>
                {x.explanation && <p className="text-sm text-muted font-semibold mt-1">{x.explanation}</p>}
              </div>
            ))}
            {rows.length > 60 && <p className="text-xs font-semibold text-muted">Showing the first 60.</p>}
          </div>
        )}
      </section>

      <div className="flex flex-col gap-2">
        <Link href="/exam" className="btn btn-primary">Take another paper</Link>
        <Link href="/" className="btn btn-ghost">Back home</Link>
      </div>
    </div>
  );
}
