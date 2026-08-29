"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Mascot, { type Mood } from "@/components/Mascot";
import { Chip, ProgressBar, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { AnswerResult, QuizSession } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];
const PRAISE = ["Nice!", "Correct!", "You got it!", "Spot on!", "Brilliant!", "Yes!"];
const CONSOLE = ["Not quite — now you know.", "Close! Remember this one.", "Good try. Read the note below.", "That's a tricky one."];

type Phase = "answering" | "revealed";

export default function Quiz({ id }: { id: string }) {
  const router = useRouter();
  const [session, setSession] = useState<QuizSession | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [phase, setPhase] = useState<Phase>("answering");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mood, setMood] = useState<Mood>("think");
  const [moodTick, setMoodTick] = useState(0);
  const [combo, setCombo] = useState(0);
  const [showQuit, setShowQuit] = useState(false);
  const [score, setScore] = useState(0);

  useEffect(() => {
    api.session(id).then((s) => {
      if (s.finished) { router.replace(`/quiz/${id}/result`); return; }
      setSession(s);
      setIndex(Math.min(s.attempts.length, s.questions.length - 1));
      setScore(s.score);
      // combo from previous attempts
      let c = 0;
      for (const a of s.attempts) c = a.is_correct ? c + 1 : 0;
      setCombo(c);
    }).catch((e) => setError(e.message));
  }, [id, router]);

  const q = session?.questions[index];
  const total = session?.questions.length ?? 0;
  const answered = phase === "revealed" ? index + 1 : index;

  const check = useCallback(async () => {
    if (!session || !q || selected === null || busy) return;
    setBusy(true);
    try {
      const r = await api.answer(session.id, q.id, selected);
      setResult(r);
      setPhase("revealed");
      setCombo(r.combo);
      setScore(r.score);
      setMood(r.is_correct ? (r.combo >= 3 ? "celebrate" : "happy") : "oops");
      setMoodTick((t) => t + 1);
      if (r.is_correct && r.combo >= 3) {
        const confetti = (await import("canvas-confetti")).default;
        confetti({ particleCount: 40, spread: 60, origin: { y: 0.3 }, scalar: 0.8, disableForReducedMotion: true });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [session, q, selected, busy]);

  const next = useCallback(async () => {
    if (!session || busy) return;
    if (index + 1 >= total) {
      setBusy(true);
      try {
        const f = await api.finish(session.id);
        sessionStorage.setItem(`finish:${session.id}`, JSON.stringify(f));
        router.replace(`/quiz/${session.id}/result`);
      } catch (e) {
        setError((e as Error).message);
        setBusy(false);
      }
      return;
    }
    setIndex(index + 1);
    setSelected(null);
    setResult(null);
    setPhase("answering");
    setMood("think");
  }, [session, busy, index, total, router]);

  // Keyboard: 1-4 select, Enter to check/next
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (showQuit) return;
      if (phase === "answering" && /^[1-4]$/.test(e.key)) setSelected(Number(e.key) - 1);
      if (e.key === "Enter") { e.preventDefault(); if (phase === "answering") void check(); else void next(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, check, next, showQuit]);

  const quit = async () => {
    if (!session) return;
    if (session.mode !== "daily" && session.attempts.length + answered === 0) await api.abandon(session.id).catch(() => {});
    router.replace("/");
  };

  if (error) return <div className="pt-10 text-center"><p className="text-danger font-bold">{error}</p><Link href="/" className="btn btn-ghost mt-4">Back home</Link></div>;
  if (!session || !q) return <Spinner label="Shuffling questions…" />;

  const optionState = (i: number) => {
    if (phase === "answering") return selected === i ? "selected" : "idle";
    if (i === result?.correct_index) return "correct";
    if (i === selected) return "wrong";
    return "dim";
  };

  return (
    <div className="min-h-dvh flex flex-col pt-3 pb-8">
      {/* Top bar */}
      <div className="flex items-center gap-3">
        <button onClick={() => setShowQuit(true)} aria-label="Exit quiz" className="h-10 w-10 rounded-xl bg-surface-2 text-muted font-extrabold grid place-items-center">✕</button>
        <div className="flex-1">
          <ProgressBar value={answered / total} />
        </div>
        <span className="text-sm font-extrabold text-muted tabular-nums">{Math.min(index + 1, total)}/{total}</span>
      </div>

      {/* Mascot + score */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          <Mascot mood={mood} trigger={moodTick} size={72} />
          <div className="text-sm font-extrabold text-muted">
            <div className="text-ink">{q.topic_icon} {q.topic}{q.published_at && <span className="text-muted font-bold"> · {new Date(q.published_at + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>}</div>
            <div>{"★".repeat(q.difficulty)}{"☆".repeat(3 - q.difficulty)} <span className="opacity-70">{["Easy", "Medium", "Hard"][q.difficulty - 1]}</span></div>
          </div>
        </div>
        <div className="text-right relative">
          <div className="text-xs font-extrabold text-muted">SCORE</div>
          <div className="text-xl font-extrabold tabular-nums">{score}</div>
          {result && result.points > 0 && <span key={moodTick} className="float-up absolute right-0 -top-2 text-success font-extrabold">+{result.points}</span>}
          {combo >= 2 && phase === "revealed" && result?.is_correct && <Chip tone="accent">🔥 {combo} in a row</Chip>}
        </div>
      </div>

      {/* Question */}
      <div key={q.id} className="pop-in mt-4 flex-1 flex flex-col">
        <h1 className="text-lg sm:text-xl font-extrabold leading-snug">{q.text}</h1>
        <div className={`mt-4 flex flex-col gap-2.5 ${phase === "revealed" && !result?.is_correct ? "" : ""}`}>
          {q.options.map((opt, i) => {
            const state = optionState(i);
            return (
              <button key={i} className={`option ${state === "wrong" ? "shake" : ""}`} data-state={state === "idle" ? undefined : state}
                onClick={() => phase === "answering" && setSelected(i)} disabled={phase === "revealed"} aria-pressed={selected === i}>
                <span className={`shrink-0 h-7 w-7 rounded-lg grid place-items-center text-xs font-extrabold ${state === "selected" ? "bg-primary text-primary-ink" : state === "correct" ? "bg-success text-white" : state === "wrong" ? "bg-danger text-white" : "bg-surface-2 text-muted"}`}>
                  {state === "correct" ? "✓" : state === "wrong" ? "✕" : LETTERS[i]}
                </span>
                <span className="font-semibold leading-snug pt-0.5">{opt}</span>
              </button>
            );
          })}
        </div>

        {/* Explanation */}
        {phase === "revealed" && result && (
          <div className={`pop-in mt-4 rounded-2xl p-4 ${result.is_correct ? "bg-success-soft" : "bg-danger-soft"}`}>
            <p className={`font-extrabold ${result.is_correct ? "text-success" : "text-danger"}`}>
              {result.is_correct ? PRAISE[moodTick % PRAISE.length] : CONSOLE[moodTick % CONSOLE.length]}
            </p>
            <p className="text-sm font-semibold mt-1 leading-relaxed">{result.explanation}</p>
            {result.source_url && <a href={result.source_url} target="_blank" rel="noopener noreferrer" className="inline-block text-xs font-extrabold mt-2 text-primary underline underline-offset-2">Read the news source ↗</a>}
            {result.streak_extended && <p className="text-xs font-extrabold mt-2 text-ink/70">🔥 Streak extended to {result.streak} day{result.streak === 1 ? "" : "s"}!</p>}
          </div>
        )}

        <div className="mt-auto pt-5">
          {phase === "answering" ? (
            <button className="btn btn-primary w-full" onClick={check} disabled={selected === null || busy}>
              {busy ? "Checking…" : selected === null ? "Pick an answer" : "Check answer"}
            </button>
          ) : (
            <button className="btn btn-primary w-full" onClick={next} disabled={busy}>
              {busy ? "Adding it up…" : index + 1 >= total ? "See my results 🎉" : "Next question →"}
            </button>
          )}
          <p className="hidden sm:block text-center text-xs text-muted font-semibold mt-2">Tip: press 1–4 to pick, Enter to continue</p>
        </div>
      </div>

      {/* Quit dialog */}
      {showQuit && (
        <div className="fixed inset-0 z-30 bg-black/40 grid place-items-center px-6" onClick={() => setShowQuit(false)}>
          <div className="card p-5 w-full max-w-sm pop-in" onClick={(e) => e.stopPropagation()}>
            <p className="font-extrabold text-lg">Take a break?</p>
            <p className="text-sm text-muted font-semibold mt-1">Your progress is saved — you can pick this quiz up again from Home.</p>
            <div className="flex gap-2 mt-4">
              <button className="btn btn-ghost flex-1" onClick={() => setShowQuit(false)}>Keep going</button>
              <button className="btn btn-primary flex-1" onClick={quit}>Exit</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
