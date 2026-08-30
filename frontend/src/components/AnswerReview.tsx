"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, Lightbulb, RotateCcw, X } from "lucide-react";
import { ErrorNote, Item, ProgressRing, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";
import type { QuizSession } from "@/lib/types";

type Filter = "all" | "wrong" | "correct";
const LETTERS = ["A", "B", "C", "D"];

export default function AnswerReview({ id }: { id: string }) {
  const router = useRouter();
  const [session, setSession] = useState<QuizSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [retrying, setRetrying] = useState(false);
  const [deeper, setDeeper] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    api.session(id).then(setSession).catch((e: Error) => setError(e?.message || "Could not load that set."));
  }, [id]);

  const rows = useMemo(() => {
    if (!session) return [];
    const byId = new Map(session.questions.map((q) => [q.id, q]));
    return session.attempts
      .map((a, i) => ({ a, q: byId.get(a.question_id), n: i + 1 }))
      .filter((r): r is { a: typeof session.attempts[0]; q: NonNullable<ReturnType<typeof byId.get>>; n: number } => Boolean(r.q));
  }, [session]);

  const wrong = rows.filter((r) => !r.a.is_correct).length;
  const shown = rows.filter((r) => filter === "all" || (filter === "wrong" ? !r.a.is_correct : r.a.is_correct));

  const explain = async (qid: number) => {
    setBusyId(qid);
    try {
      const r = await api.explain(qid);
      setDeeper((d) => ({ ...d, [qid]: r.explanation }));
    } catch (e) {
      setError((e as Error)?.message || "Could not load a deeper explanation.");
    } finally {
      setBusyId(null);
    }
  };

  const retry = async () => {
    setRetrying(true);
    setError(null);
    try {
      const s = await api.startQuiz({ mode: "retry", session: id });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Could not build a retry set.");
      setRetrying(false);
    }
  };

  if (error && !session) return (
    <div className="pt-10 text-center">
      <p className="text-danger font-semibold">{error}</p>
      <Link href="/history" className="btn btn-ghost mt-4">Back to history</Link>
    </div>
  );
  if (!session) return <SkeletonPage />;

  const correct = rows.length - wrong;
  const acc = rows.length ? correct / rows.length : 0;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <Link href="/history" className="inline-flex items-center gap-1.5 text-sm font-extrabold text-muted hover:text-ink">
          <ArrowLeft size={16} /> History
        </Link>
      </Item>

      <Item>
        <div className="card p-5 flex items-center gap-4">
          <ProgressRing value={acc} size={78} color={acc >= 0.6 ? "var(--success)" : "var(--danger)"}>
            <div className="text-center leading-none">
              <div className="text-base font-extrabold">{correct}/{rows.length}</div>
              <div className="text-[9px] font-extrabold text-muted mt-0.5">CORRECT</div>
            </div>
          </ProgressRing>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-extrabold leading-tight">
              {session.topic ?? (session.mode === "daily" ? "Daily challenge" : "Practice set")}
            </h1>
            <p className="text-sm text-muted font-semibold mt-0.5">
              Every question from this set, with the right answer and why.
            </p>
            {wrong > 0 && (
              <button className="btn btn-primary !min-h-10 mt-3 text-sm" onClick={retry} disabled={retrying}>
                <RotateCcw size={15} /> {retrying ? "Building…" : `Redo the ${wrong} I got wrong`}
              </button>
            )}
          </div>
        </div>
      </Item>

      <ErrorNote message={error} />

      <Item>
        <div className="flex gap-1.5">
          {([["all", `All ${rows.length}`], ["wrong", `Wrong ${wrong}`], ["correct", `Correct ${correct}`]] as const).map(([f, label]) => (
            <button key={f} onClick={() => setFilter(f as Filter)}
              className={`text-xs font-extrabold px-3 py-1.5 rounded-xl transition ${filter === f ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted hover:text-ink"}`}>
              {label}
            </button>
          ))}
        </div>
      </Item>

      {shown.length === 0 ? (
        <Item><p className="text-center text-muted font-semibold py-8">Nothing in this filter.</p></Item>
      ) : shown.map(({ a, q, n }) => (
        <Item key={a.question_id}>
          <div className="card p-4">
            <div className="flex items-center justify-between text-[11px] font-extrabold text-muted mb-1.5">
              <span>Q{n} · {q.topic_icon} {q.topic}</span>
              <span className={a.is_correct ? "text-success" : "text-danger"}>
                {a.is_correct ? `+${a.points} pts` : "Missed"}
              </span>
            </div>
            {a.source_ref && <p className="text-[11px] font-extrabold text-accent uppercase tracking-wide mb-1">📄 {a.source_ref}</p>}
            <p className="font-extrabold leading-snug">{q.text}</p>

            <div className="mt-3 flex flex-col gap-1.5">
              {q.options.map((opt, i) => {
                const isAnswer = i === a.correct_index;
                const isYours = i === a.selected_index;
                const tone = isAnswer ? "border-success bg-success-soft"
                  : isYours ? "border-danger bg-danger-soft" : "border-line";
                return (
                  <div key={i} className={`rounded-xl border px-3 py-2 flex items-start gap-2.5 ${tone}`}>
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

            {a.explanation && <p className="text-sm text-muted font-semibold mt-3 leading-relaxed">{a.explanation}</p>}
            {a.source_url && (
              <a href={a.source_url} target="_blank" rel="noopener noreferrer"
                className="inline-block text-xs font-extrabold mt-2 text-primary underline underline-offset-2">
                {a.source_ref ? "Open the official paper ↗" : "Read the news source ↗"}
              </a>
            )}

            {deeper[a.question_id] ? (
              <div className="mt-3 pt-3 border-t border-line whitespace-pre-line text-sm font-semibold leading-relaxed pop-in">
                {deeper[a.question_id]}
              </div>
            ) : (
              <button className="mt-3 text-xs font-extrabold text-primary underline underline-offset-2 disabled:opacity-50 inline-flex items-center gap-1"
                disabled={busyId === a.question_id} onClick={() => explain(a.question_id)}>
                <Lightbulb size={13} /> {busyId === a.question_id ? "Thinking…" : "Explain this more"}
              </button>
            )}
          </div>
        </Item>
      ))}
    </Stagger>
  );
}
