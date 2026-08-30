"use client";

import { useState } from "react";
import { Check, Lightbulb, X } from "lucide-react";
import { api } from "@/lib/api";
import type { AnsweredQuestion } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];

/** One reviewed question: what you picked, what was right, why, and an optional deeper read. */
export default function AnsweredCard({ q, showTopic = false }: { q: AnsweredQuestion; showTopic?: boolean }) {
  const [deeper, setDeeper] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  return (
    <div className="card p-4">
      <button className="w-full text-left" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <div className="flex items-center justify-between text-[11px] font-extrabold text-muted mb-1.5">
          <span>{showTopic ? `${q.topic_icon} ${q.topic}` : `${"★".repeat(q.difficulty)}${"☆".repeat(3 - q.difficulty)}`}</span>
          <span className={q.is_correct ? "text-success" : "text-danger"}>
            {q.is_correct ? "Correct" : "Missed"}
            {q.times_seen > 1 && ` · seen ${q.times_seen}×`}
          </span>
        </div>
        {q.source_ref && <p className="text-[11px] font-extrabold text-accent uppercase tracking-wide mb-1">📄 {q.source_ref}</p>}
        <p className="font-extrabold leading-snug">{q.text}</p>
        {!open && (
          <p className="text-xs font-bold text-muted mt-2">
            {q.is_correct
              ? `You answered: ${q.options[q.correct_index]}`
              : `You said ${q.options[q.selected_index]} · correct is ${q.options[q.correct_index]}`}
            <span className="text-primary ml-1">— tap to expand</span>
          </p>
        )}
      </button>

      {open && (
        <>
          <div className="mt-3 flex flex-col gap-1.5">
            {q.options.map((opt, i) => {
              const isAnswer = i === q.correct_index;
              const isYours = i === q.selected_index;
              return (
                <div key={i} className={`rounded-xl border px-3 py-2 flex items-start gap-2.5
                  ${isAnswer ? "border-success bg-success-soft" : isYours ? "border-danger bg-danger-soft" : "border-line"}`}>
                  <span className={`shrink-0 h-6 w-6 rounded-lg grid place-items-center text-[11px] font-extrabold
                    ${isAnswer ? "bg-success text-white" : isYours ? "bg-danger text-white" : "bg-surface-2 text-muted"}`}>
                    {isAnswer ? <Check size={13} strokeWidth={3} /> : isYours ? <X size={13} strokeWidth={3} /> : LETTERS[i]}
                  </span>
                  <span className="text-sm font-semibold leading-snug pt-0.5">{opt}</span>
                  {isYours && !isAnswer && <span className="ml-auto text-[10px] font-extrabold text-danger shrink-0">YOUR PICK</span>}
                </div>
              );
            })}
          </div>

          {q.explanation && <p className="text-sm text-muted font-semibold mt-3 leading-relaxed">{q.explanation}</p>}
          {q.source_url && (
            <a href={q.source_url} target="_blank" rel="noopener noreferrer"
              className="inline-block text-xs font-extrabold mt-2 text-primary underline underline-offset-2">
              {q.source_ref ? "Open the official paper ↗" : "Read the news source ↗"}
            </a>
          )}

          {deeper ? (
            <div className="mt-3 pt-3 border-t border-line whitespace-pre-line text-sm font-semibold leading-relaxed pop-in">{deeper}</div>
          ) : (
            <button className="mt-3 text-xs font-extrabold text-primary underline underline-offset-2 disabled:opacity-50 inline-flex items-center gap-1"
              disabled={busy}
              onClick={async () => {
                setBusy(true); setError(null);
                try { setDeeper((await api.explain(q.question_id)).explanation); }
                catch (e) { setError((e as Error)?.message || "Could not load a deeper explanation."); }
                finally { setBusy(false); }
              }}>
              <Lightbulb size={13} /> {busy ? "Thinking…" : "Explain this more"}
            </button>
          )}
          {error && <p className="mt-2 text-xs font-bold text-danger">{error}</p>}
        </>
      )}
    </div>
  );
}
