"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HoldButton, LoadingQuips } from "@/components/ui";
import { api } from "@/lib/api";
import type { ExamState } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];

function clock(total: number) {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export default function Exam({ id }: { id: string }) {
  const router = useRouter();
  const [state, setState] = useState<ExamState | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [marked, setMarked] = useState<Set<number>>(new Set());
  const [index, setIndex] = useState(0);
  const [left, setLeft] = useState(0);
  const [showPalette, setShowPalette] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitted = useRef(false);

  useEffect(() => {
    api.exam(id).then((s) => {
      if (s.submitted) { router.replace(`/exam/${id}/result`); return; }
      setState(s);
      setAnswers(s.answers);
      setMarked(new Set(s.marked));
      setLeft(s.seconds_remaining);
      const firstUnanswered = s.questions.findIndex((q) => s.answers[q.id] === undefined);
      setIndex(firstUnanswered === -1 ? 0 : firstUnanswered);
    }).catch((e) => setError(e?.message || "Could not load the exam."));
  }, [id, router]);

  const submit = useCallback(async () => {
    if (submitted.current) return;
    submitted.current = true;
    setSubmitting(true);
    try {
      await api.submitExam(id);
      router.replace(`/exam/${id}/result`);
    } catch (e) {
      setError((e as Error)?.message || "Could not submit the paper.");
      submitted.current = false;
      setSubmitting(false);
    }
  }, [id, router]);

  // The deadline lives on the server; this is only the visible countdown.
  useEffect(() => {
    if (!state) return;
    const t = setInterval(() => {
      setLeft((v) => {
        if (v <= 1) { clearInterval(t); void submit(); return 0; }
        return v - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [state, submit]);

  // Re-sync the clock with the server when the tab comes back (mobile suspends timers).
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && !submitted.current) {
        api.exam(id).then((s) => setLeft(s.seconds_remaining)).catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [id]);

  const q = state?.questions[index];

  const save = useCallback(async (questionId: number, selected: number, mark: boolean) => {
    setAnswers((a) => (selected === -1 ? (() => { const c = { ...a }; delete c[questionId]; return c; })() : { ...a, [questionId]: selected }));
    setMarked((m) => {
      const c = new Set(m);
      if (mark) c.add(questionId); else c.delete(questionId);
      return c;
    });
    try {
      await api.saveExamAnswer(id, questionId, selected, mark);
    } catch {
      /* keep the local choice; the next save or submit will reconcile */
    }
  }, [id]);

  const counts = useMemo(() => {
    const total = state?.total ?? 0;
    const answered = Object.values(answers).filter((v) => v >= 0).length;
    return { total, answered, blank: total - answered, marked: marked.size };
  }, [answers, marked, state]);

  // Keyboard: 1-4 answer, arrows navigate, M marks for review
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!q || confirming) return;
      if (/^[1-4]$/.test(e.key)) void save(q.id, Number(e.key) - 1, marked.has(q.id));
      if (e.key === "ArrowRight") setIndex((i) => Math.min(i + 1, (state?.total ?? 1) - 1));
      if (e.key === "ArrowLeft") setIndex((i) => Math.max(i - 1, 0));
      if (e.key.toLowerCase() === "m") void save(q.id, answers[q.id] ?? -1, !marked.has(q.id));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q, answers, marked, save, state, confirming]);

  if (error) return <div className="pt-10 text-center"><p className="text-danger font-bold">{error}</p><Link href="/exam" className="btn btn-ghost mt-4">Back</Link></div>;
  if (!state || !q) return <LoadingQuips quips={["Preparing your paper…", "Setting the clock…", "Sealing the answer key…"]} />;

  const urgent = left <= 300;
  const chosen = answers[q.id];

  return (
    <div className="min-h-dvh flex flex-col pt-3 pb-4">
      {/* Timer bar */}
      <div className="flex items-center gap-3">
        <button onClick={() => setConfirming(true)} className="h-10 px-3 rounded-xl bg-surface-2 text-sm font-extrabold text-muted">Submit</button>
        <div className="flex-1 text-center">
          <div className={`text-2xl font-extrabold tabular-nums ${urgent ? "text-danger" : ""}`} role="timer" aria-live="off">{clock(left)}</div>
          <div className="text-[11px] font-extrabold text-muted">{counts.answered}/{counts.total} answered</div>
        </div>
        <button onClick={() => setShowPalette(true)} aria-label="Question palette"
          className="h-10 px-3 rounded-xl bg-surface-2 text-sm font-extrabold text-muted">☰ {index + 1}</button>
      </div>
      <div className="h-1.5 mt-2 rounded-full bg-surface-2 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${((state.duration_seconds - left) / Math.max(state.duration_seconds, 1)) * 100}%`, background: urgent ? "var(--danger)" : "var(--primary)" }} />
      </div>

      {/* Question */}
      <div key={q.id} className="pop-in mt-4 flex-1 flex flex-col">
        <div className="flex items-center justify-between text-xs font-extrabold text-muted">
          <span>Question {index + 1} of {counts.total}</span>
          <span>{q.topic_icon} {q.topic}</span>
        </div>
        <h1 className="text-lg font-extrabold leading-snug mt-2">{q.text}</h1>
        <div className="mt-4 flex flex-col gap-2.5">
          {q.options.map((opt, i) => (
            <button key={i} className="option" data-state={chosen === i ? "selected" : undefined}
              onClick={() => save(q.id, i, marked.has(q.id))} aria-pressed={chosen === i}>
              <span className={`shrink-0 h-7 w-7 rounded-lg grid place-items-center text-xs font-extrabold ${chosen === i ? "bg-primary text-primary-ink" : "bg-surface-2 text-muted"}`}>{LETTERS[i]}</span>
              <span className="font-semibold leading-snug pt-0.5">{opt}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={() => save(q.id, -1, marked.has(q.id))} disabled={chosen === undefined}
            className="text-xs font-extrabold text-muted disabled:opacity-40 px-3 py-2 rounded-xl bg-surface-2">Clear</button>
          <button onClick={() => save(q.id, chosen ?? -1, !marked.has(q.id))}
            className={`text-xs font-extrabold px-3 py-2 rounded-xl ${marked.has(q.id) ? "bg-accent-soft text-ink" : "bg-surface-2 text-muted"}`}>
            {marked.has(q.id) ? "★ Marked for review" : "☆ Mark for review"}
          </button>
        </div>

        <div className="mt-auto pt-5 flex gap-2">
          <button className="btn btn-ghost flex-1" onClick={() => setIndex((i) => Math.max(i - 1, 0))} disabled={index === 0}>← Previous</button>
          {index + 1 < counts.total
            ? <button className="btn btn-primary flex-1" onClick={() => setIndex((i) => i + 1)}>Next →</button>
            : <button className="btn btn-primary flex-1" onClick={() => setConfirming(true)}>Finish paper</button>}
        </div>
        <p className="hidden sm:block text-center text-[11px] text-muted font-semibold mt-2">1–4 to answer · ← → to move · M to mark · nothing is revealed until you submit</p>
      </div>

      {/* Palette */}
      {showPalette && (
        <div className="fixed inset-0 z-30 bg-black/40 flex items-end sm:items-center justify-center" onClick={() => setShowPalette(false)}>
          <div className="card w-full sm:max-w-md max-h-[80dvh] overflow-y-auto p-4 pop-in" onClick={(e) => e.stopPropagation()}>
            <p className="font-extrabold mb-1">Question palette</p>
            <p className="text-xs font-semibold text-muted mb-3">
              <span className="inline-block w-2.5 h-2.5 rounded bg-success align-middle" /> answered ·
              <span className="inline-block w-2.5 h-2.5 rounded bg-accent align-middle ml-2" /> marked ·
              <span className="inline-block w-2.5 h-2.5 rounded bg-line align-middle ml-2" /> blank
            </p>
            <div className="grid grid-cols-8 sm:grid-cols-10 gap-1.5">
              {state.questions.map((qq, i) => {
                const done = answers[qq.id] !== undefined;
                const mk = marked.has(qq.id);
                return (
                  <button key={qq.id} onClick={() => { setIndex(i); setShowPalette(false); }}
                    className={`aspect-square rounded-lg text-xs font-extrabold transition ${i === index ? "ring-2 ring-primary " : ""}${mk ? "bg-accent text-ink" : done ? "bg-success text-white" : "bg-surface-2 text-muted"}`}>
                    {i + 1}
                  </button>
                );
              })}
            </div>
            <button className="btn btn-ghost w-full mt-4" onClick={() => setShowPalette(false)}>Close</button>
          </div>
        </div>
      )}

      {/* Submit confirmation */}
      {confirming && (
        <div className="fixed inset-0 z-30 bg-black/40 grid place-items-center px-6" onClick={() => setConfirming(false)}>
          <div className="card p-5 w-full max-w-sm pop-in" onClick={(e) => e.stopPropagation()}>
            <p className="font-extrabold text-lg">Submit the paper?</p>
            <ul className="text-sm font-semibold text-muted mt-2 space-y-0.5">
              <li>Answered: <b className="text-ink">{counts.answered}</b></li>
              <li>Left blank: <b className="text-ink">{counts.blank}</b> (no penalty)</li>
              <li>Marked for review: <b className="text-ink">{counts.marked}</b></li>
            </ul>
            <p className="text-xs font-semibold text-muted mt-2">Wrong answers lose 1/3 mark each. Blanks lose nothing.</p>
            <div className="flex gap-2 mt-4">
              <button className="btn btn-ghost flex-1" onClick={() => setConfirming(false)} disabled={submitting}>Keep going</button>
              <HoldButton className="btn-primary flex-1" onComplete={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Hold to submit"}
              </HoldButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
