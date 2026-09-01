"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Check, Lightbulb, X } from "lucide-react";
import Mascot, { type Mood } from "@/components/Mascot";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Chip, LoadingQuips, Num, ProgressBar } from "@/components/ui";
import { api, QueuedOffline } from "@/lib/api";
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
  const [milestone, setMilestone] = useState<{ title: string; body: string; days: number } | null>(null);
  const [showQuit, setShowQuit] = useState(false);
  const [queued, setQueued] = useState(false);
  const [deeper, setDeeper] = useState<string | null>(null);
  const [deeperBusy, setDeeperBusy] = useState(false);
  const [deeperError, setDeeperError] = useState<string | null>(null);
  const shownAt = useRef<number>(0);
  const [score, setScore] = useState(0);
  const reduceMotion = useReducedMotion();

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
      shownAt.current = Date.now();
    }).catch((e) => setError(e?.message || "Something went wrong. Please try again."));
  }, [id, router]);

  const q = session?.questions[index];
  const total = session?.questions.length ?? 0;
  const answered = phase === "revealed" ? index + 1 : index;

  const check = useCallback(async () => {
    if (!session || !q || selected === null || busy) return;
    setBusy(true);
    try {
      const elapsed = shownAt.current ? Date.now() - shownAt.current : undefined;
      const r = await api.answer(session.id, q.id, selected, elapsed);
      setResult(r);
      setPhase("revealed");
      setCombo(r.combo);
      setScore(r.score);
      setMood(r.is_correct ? (r.combo >= 3 ? "celebrate" : "happy") : "oops");
      setMoodTick((t) => t + 1);
      if (r.milestone && r.milestone_title) {
        setMilestone({ title: r.milestone_title, body: r.milestone_body ?? "", days: r.milestone });
        const confetti = (await import("canvas-confetti")).default;
        confetti({ particleCount: 160, spread: 100, origin: { y: 0.35 }, disableForReducedMotion: true });
      }
      if (r.is_correct && r.combo >= 3) {
        const confetti = (await import("canvas-confetti")).default;
        confetti({ particleCount: 40, spread: 60, origin: { y: 0.3 }, scalar: 0.8, disableForReducedMotion: true });
      }
    } catch (e) {
      if (e instanceof QueuedOffline) {
        // Saved locally; we genuinely do not know whether it was right, so do not pretend to.
        setQueued(true);
      } else {
        setError((e as Error)?.message || "Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }, [session, q, selected, busy]);

  const next = useCallback(async () => {
    if (!session || busy) return;
    if (index + 1 >= total) {
      if (queued) {
        setError("Some answers are still waiting to sync. Reconnect and reopen this quiz to finish it.");
        return;
      }
      setBusy(true);
      try {
        const f = await api.finish(session.id);
        sessionStorage.setItem(`finish:${session.id}`, JSON.stringify(f));
        router.replace(`/quiz/${session.id}/result`);
      } catch (e) {
        setError((e as Error)?.message || "Something went wrong. Please try again.");
        setBusy(false);
      }
      return;
    }
    shownAt.current = Date.now();
    setIndex(index + 1);
    setSelected(null);
    setQueued(false);
    setDeeper(null);
    setDeeperError(null);
    setResult(null);
    setPhase("answering");
    setMood("think");
  }, [session, busy, index, total, router, queued]);

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
  if (!session || !q) return <LoadingQuips quips={["Shuffling questions…", "Picking from past papers…", "Warming up Kunju…"]} />;

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

      {/* Mascot + score. Kunju shares a layoutId with the slot in the feedback card, so on
          reveal he glides down to deliver the verdict beside the explanation and returns here
          on the next question. */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          <div className="h-[72px] w-[72px] shrink-0">
            {phase !== "revealed" && (
              <motion.div layoutId="kunju" transition={{ duration: reduceMotion ? 0 : 0.45, ease: [0.2, 0.8, 0.2, 1] }}>
                <Mascot mood={mood} trigger={moodTick} size={72} />
              </motion.div>
            )}
          </div>
          <div className="text-sm font-extrabold text-muted">
            <div className="text-ink">{q.topic_icon} {q.topic}{q.published_at && !q.source_ref && <span className="text-muted font-bold"> · {new Date(q.published_at + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>}</div>
            <div>{"★".repeat(q.difficulty)}{"☆".repeat(3 - q.difficulty)} <span className="opacity-70">{["Easy", "Medium", "Hard"][q.difficulty - 1]}</span></div>
          </div>
        </div>
        <div className="text-right relative">
          <div className="text-xs font-extrabold text-muted">SCORE</div>
          <div className="text-xl font-extrabold"><Num value={score} /></div>
          {result && result.points > 0 && <span key={moodTick} className="float-up absolute right-0 -top-2 text-success font-extrabold">+{result.points}</span>}
          {combo >= 2 && phase === "revealed" && result?.is_correct && <Chip tone="accent">🔥 {combo} in a row</Chip>}
        </div>
      </div>

      {/* Question. popLayout pops the exiting card out of flow, so the incoming one takes its
          place immediately and the footer button never jumps while both are on screen. */}
      <AnimatePresence mode="popLayout" initial={false}>
      <motion.div key={q.id} className="mt-4 flex-1 flex flex-col"
        initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -28 }}
        transition={{ type: "spring", visualDuration: 0.3, bounce: 0 }}>
        {q.source_ref && (
          <p className="text-[11px] font-extrabold text-accent uppercase tracking-wide mb-1.5">📄 Asked in {q.source_ref}</p>
        )}
        <h1 className="text-lg sm:text-xl font-extrabold leading-snug">{q.text}</h1>
        <div className={`mt-4 flex flex-col gap-2.5 ${phase === "revealed" && !result?.is_correct ? "" : ""}`}>
          {q.options.map((opt, i) => {
            const state = optionState(i);
            return (
              <motion.button key={i} className={`option ${state === "wrong" ? "shake" : ""}`}
                data-state={state === "idle" ? undefined : state}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * i, duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
                whileTap={phase === "answering" ? { scale: 0.985 } : undefined}
                onClick={() => phase === "answering" && setSelected(i)}
                disabled={phase === "revealed"} aria-pressed={selected === i}>
                <span className={`shrink-0 h-7 w-7 rounded-lg grid place-items-center text-xs font-extrabold transition-colors ${state === "selected" ? "bg-primary text-primary-ink" : state === "correct" ? "bg-success text-white" : state === "wrong" ? "bg-danger text-white" : "bg-surface-2 text-muted"}`}>
                  {state === "correct" ? <Check size={15} strokeWidth={3} /> : state === "wrong" ? <X size={15} strokeWidth={3} /> : LETTERS[i]}
                </span>
                <span className="font-semibold leading-snug pt-0.5">{opt}</span>
              </motion.button>
            );
          })}
        </div>

        {/* Explanation */}
        <AnimatePresence>
        {phase === "revealed" && result && (
          <motion.div key="feedback"
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: "auto", marginTop: 16 }}
            transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
            className={`overflow-hidden rounded-2xl p-4 ${result.is_correct ? "bg-success-soft" : "bg-danger-soft"}`}>
            <div className="flex items-start gap-3">
            <motion.div layoutId="kunju" transition={{ duration: reduceMotion ? 0 : 0.45, ease: [0.2, 0.8, 0.2, 1] }} className="shrink-0">
              <span key={moodTick} className="mascot-pop block">
                <Mascot mood={mood} trigger={moodTick} size={64} />
              </span>
            </motion.div>
            <div className="min-w-0 flex-1">
            <p className={`font-extrabold ${result.is_correct ? "text-success" : "text-danger"}`}>
              {result.is_correct ? PRAISE[moodTick % PRAISE.length] : CONSOLE[moodTick % CONSOLE.length]}
            </p>
            <p className="text-sm font-semibold mt-1 leading-relaxed">{result.explanation}</p>
            {result.source_ref && <p className="text-xs font-bold mt-2 text-ink/70">From the official Kerala PSC paper · {result.source_ref}</p>}
            {result.source_url && <a href={result.source_url} target="_blank" rel="noopener noreferrer" className="inline-block text-xs font-extrabold mt-2 text-primary underline underline-offset-2">{result.source_ref ? "Open the official paper ↗" : "Read the news source ↗"}</a>}
            {result.streak_repaired ? (
              <p className="text-xs font-extrabold mt-2 text-ink/70">
                🛟 You missed a day, so we used a streak repair — your {result.streak}-day run is intact.
                {result.repairs_left} left this month.
              </p>
            ) : result.streak_extended ? (
              <p className="text-xs font-extrabold mt-2 text-ink/70">🔥 Streak extended to {result.streak} day{result.streak === 1 ? "" : "s"}!</p>
            ) : null}

            {deeper ? (
              <div className="mt-3 pt-3 border-t border-ink/10 whitespace-pre-line text-sm font-semibold leading-relaxed pop-in">{deeper}</div>
            ) : (
              <button
                className="mt-3 text-xs font-extrabold text-primary underline underline-offset-2 disabled:opacity-50"
                disabled={deeperBusy}
                onClick={async () => {
                  setDeeperBusy(true);
                  setDeeperError(null);
                  try {
                    setDeeper((await api.explain(q.id)).explanation);
                  } catch (e) {
                    setDeeperError((e as Error)?.message || "Could not load a deeper explanation.");
                  } finally {
                    setDeeperBusy(false);
                  }
                }}>
                {deeperBusy ? "Thinking…" : <span className="inline-flex items-center gap-1"><Lightbulb size={13} /> Explain this more</span>}
              </button>
            )}
            {deeperError && <p className="mt-2 text-xs font-bold text-danger">{deeperError}</p>}
            </div>
            </div>
          </motion.div>
        )}
        </AnimatePresence>

        <div className="mt-auto pt-5">
          {queued ? (
            <>
              <p className="rounded-xl bg-accent-soft text-accent-ink px-3 py-2 text-sm font-bold mb-2">
                Saved offline. We can&apos;t mark it until you&apos;re back online — it will sync automatically.
              </p>
              <button className="btn btn-primary w-full" onClick={next} disabled={busy}>
                {index + 1 >= total ? "Finish later" : "Next question"}
              </button>
            </>
          ) : phase === "answering" ? (
            <button className="btn btn-primary w-full" onClick={check} disabled={selected === null || busy}>
              {busy ? "Checking…" : selected === null ? "Pick an answer" : "Check answer"}
            </button>
          ) : (
            <button className="btn btn-primary w-full" onClick={next} disabled={busy}>
              {busy ? "Adding it up…" : index + 1 >= total ? "See my results 🎉" : <>Next question <ArrowRight size={17} /></>}
            </button>
          )}
          <p className="hidden sm:block text-center text-xs text-muted font-semibold mt-2">Tip: press 1–4 to pick, Enter to continue</p>
        </div>
      </motion.div>
      </AnimatePresence>

      {/* Streak milestone */}
      <AnimatePresence>
      {milestone && (
        <motion.div className="fixed inset-0 z-40 bg-black/50 grid place-items-center px-6" onClick={() => setMilestone(null)}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <motion.div className="card p-6 w-full max-w-sm text-center" onClick={(e) => e.stopPropagation()}
            initial={{ scale: 0.94, y: 10, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ opacity: 0, scale: 0.96 }} transition={{ type: "spring", visualDuration: 0.3, bounce: 0.2 }}>
            <Mascot mood="celebrate" size={120} />
            <p className="text-3xl font-extrabold mt-1">🔥 {milestone.days}</p>
            <p className="text-xl font-extrabold mt-1">{milestone.title}</p>
            <p className="text-sm font-semibold text-muted mt-2 leading-relaxed">{milestone.body}</p>
            <button className="btn btn-primary w-full mt-5" onClick={() => setMilestone(null)}>Keep going</button>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>

      {/* Quit dialog */}
      <AnimatePresence>
      {showQuit && (
        <motion.div className="fixed inset-0 z-30 bg-black/40 grid place-items-center px-6" onClick={() => setShowQuit(false)}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <motion.div className="card p-5 w-full max-w-sm" onClick={(e) => e.stopPropagation()}
            initial={{ scale: 0.94, y: 10, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ opacity: 0, scale: 0.96 }} transition={{ type: "spring", visualDuration: 0.3, bounce: 0.2 }}>
            <p className="font-extrabold text-lg">Take a break?</p>
            <p className="text-sm text-muted font-semibold mt-1">Your progress is saved — you can pick this quiz up again from Home.</p>
            <div className="flex gap-2 mt-4">
              <button className="btn btn-ghost flex-1" onClick={() => setShowQuit(false)}>Keep going</button>
              <button className="btn btn-primary flex-1" onClick={quit}>Exit</button>
            </div>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>
    </div>
  );
}
