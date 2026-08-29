"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import { ProgressBar, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { FinishResult, QuizSession } from "@/lib/types";

const BADGE_NAMES: Record<string, string> = {
  "first-quiz": "🌱 First Step", "ten-quizzes": "📚 Regular", "fifty-quizzes": "🏛️ Dedicated", "perfect-score": "💯 Flawless",
  "streak-3": "🔥 Warming Up", "streak-7": "🔥 On Fire", "streak-30": "🌟 Unstoppable", "hundred-questions": "💪 Century",
  "five-hundred-questions": "🏃 Marathoner", "sharp-shooter": "🎯 Sharp Shooter", "thousand-points": "💎 Point Collector",
};

function headline(acc: number) {
  if (acc === 1) return "Perfect round!";
  if (acc >= 0.8) return "Excellent work!";
  if (acc >= 0.6) return "Solid effort!";
  if (acc >= 0.4) return "Good practice.";
  return "Every attempt teaches something.";
}

export default function Result({ id }: { id: string }) {
  const router = useRouter();
  const [res, setRes] = useState<FinishResult | null>(null);
  const [session, setSession] = useState<QuizSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    const cached = sessionStorage.getItem(`finish:${id}`);
    const p = cached ? Promise.resolve(JSON.parse(cached) as FinishResult) : api.finish(id);
    Promise.all([p, api.session(id)]).then(async ([f, s]) => {
      setRes(f);
      setSession(s);
      if (f.accuracy >= 0.8 && !f.already_finished) {
        const confetti = (await import("canvas-confetti")).default;
        confetti({ particleCount: 120, spread: 80, origin: { y: 0.4 }, disableForReducedMotion: true });
      }
    }).catch((e) => setError(e.message));
  }, [id]);

  const again = async () => {
    if (!session) return;
    setStarting(true);
    try {
      const topicSlug = session.mode === "topic" ? session.topic : undefined;
      // topic name → slug lookup
      let slug: string | undefined;
      if (topicSlug) {
        const topics = await api.topics();
        slug = topics.find((t) => t.name === topicSlug)?.slug;
      }
      const s = await api.startQuiz(slug ? { mode: "topic", topic: slug } : { mode: "mixed" });
      router.replace(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(false);
    }
  };

  if (error) return <div className="pt-10 text-center"><p className="text-danger font-bold">{error}</p><Link href="/" className="btn btn-ghost mt-4">Back home</Link></div>;
  if (!res || !session) return <Spinner label="Adding it up…" />;

  const acc = res.accuracy;
  const questionsById = new Map(session.questions.map((q) => [q.id, q]));

  return (
    <div className="pt-6 pb-10 flex flex-col items-center text-center pop-in">
      <Mascot mood={acc >= 0.6 ? "celebrate" : "happy"} size={150} />
      <h1 className="text-2xl font-extrabold mt-2">{headline(acc)}</h1>
      <p className="text-muted font-semibold mt-1">You got {res.correct} of {res.total} right.</p>

      <div className="card w-full p-5 mt-5 grid grid-cols-3 gap-3">
        <div><div className="text-2xl font-extrabold text-primary">+{res.score}</div><div className="text-xs font-extrabold text-muted">POINTS</div></div>
        <div><div className="text-2xl font-extrabold">{Math.round(acc * 100)}%</div><div className="text-xs font-extrabold text-muted">ACCURACY</div></div>
        <div><div className="text-2xl font-extrabold text-accent">🔥 {res.streak}</div><div className="text-xs font-extrabold text-muted">DAY STREAK</div></div>
        {res.bonus > 0 && <p className="col-span-3 text-xs font-extrabold text-success">Includes a +{res.bonus} bonus{session.mode === "daily" ? " for finishing today's challenge" : ""}{acc === 1 ? " (perfect round!)" : ""}.</p>}
      </div>

      <div className="card w-full p-4 mt-3 text-left">
        <div className="flex justify-between text-xs font-extrabold text-muted mb-2">
          <span>Level {res.level} · {res.level_title}</span>
          <span>{res.points_to_next_level} pts to go</span>
        </div>
        <ProgressBar value={1 - res.points_to_next_level / Math.max(res.points_to_next_level + res.total_points, 1)} color="var(--accent)" />
        <p className="text-xs text-muted font-semibold mt-2">{res.total_points} total points</p>
      </div>

      {res.new_badges.length > 0 && (
        <div className="card w-full p-4 mt-3 bg-accent-soft border-accent/40">
          <p className="font-extrabold">New badge{res.new_badges.length > 1 ? "s" : ""} unlocked!</p>
          <div className="flex flex-wrap justify-center gap-2 mt-2">
            {res.new_badges.map((b) => <span key={b} className="rounded-full bg-surface px-3 py-1 text-sm font-extrabold">{BADGE_NAMES[b] ?? b}</span>)}
          </div>
        </div>
      )}

      <div className="w-full flex flex-col gap-2 mt-6">
        <button className="btn btn-primary" onClick={again} disabled={starting}>{starting ? "Shuffling…" : "One more round →"}</button>
        <button className="btn btn-ghost" onClick={() => setShowReview((v) => !v)}>{showReview ? "Hide review" : "Review answers"}</button>
        <Link href="/" className="btn btn-ghost">Back home</Link>
      </div>

      {showReview && (
        <div className="w-full mt-5 flex flex-col gap-3 text-left pop-in">
          {session.attempts.map((a, i) => {
            const q = questionsById.get(a.question_id);
            if (!q) return null;
            return (
              <div key={a.question_id} className="card p-4">
                <p className="text-xs font-extrabold text-muted">Q{i + 1} · {q.topic}</p>
                <p className="font-extrabold mt-1">{q.text}</p>
                <p className={`text-sm font-bold mt-2 ${a.is_correct ? "text-success" : "text-danger"}`}>
                  {a.is_correct ? "✓ " : "✕ Your answer: "}{a.is_correct ? q.options[a.correct_index] : q.options[a.selected_index]}
                </p>
                {!a.is_correct && <p className="text-sm font-bold text-success">✓ Correct: {q.options[a.correct_index]}</p>}
                <p className="text-sm text-muted font-semibold mt-1">{a.explanation}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
