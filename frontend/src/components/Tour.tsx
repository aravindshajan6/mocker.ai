"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, BrainCircuit, CalendarCheck, Flame, Timer, TrendingUp } from "lucide-react";
import Mascot, { type Mood } from "@/components/Mascot";
import { useAppData } from "@/components/AppData";

const DONE_KEY = "mocker:tour-done";

/** One card per idea, Kunju acting each one out. Kept to five — a tour is a trailer, not the film. */
const STEPS: { mood: Mood; icon: typeof Flame; tint: string; title: string; body: string }[] = [
  { mood: "wave", icon: CalendarCheck, tint: "bg-primary-soft text-primary", title: "Hi, I'm Kunju!",
    body: "Welcome to Mocker — your calm corner for PSC, SSC and UPSC prep. Let me show you around before your first question. It takes half a minute." },
  { mood: "happy", icon: Flame, tint: "bg-accent-soft text-accent-ink", title: "Start with the daily challenge",
    body: "Every morning there's a fresh shared set — the same for every aspirant, so scores really compare. Finish it to grow a streak; miss a day and I'll quietly repair it, twice a month." },
  { mood: "think", icon: BrainCircuit, tint: "bg-primary-soft text-primary", title: "Practise what costs you marks",
    body: "Drill any subject — from Indian History to General English — or let me build sets from the topics you keep slipping on. Questions you struggle with come back for revision right before you'd forget them." },
  { mood: "oops", icon: Timer, tint: "bg-info-soft text-info", title: "Rehearse the real exam",
    body: "Exam mode runs full-length timed papers with the hall's own rules — negative marking, a question palette, deliberate blanks. Better to meet them here first." },
  { mood: "celebrate", icon: TrendingUp, tint: "bg-accent-soft text-accent-ink", title: "Watch yourself improve",
    body: "Points, levels, badges and a weekly leaderboard keep score of your consistency, and your progress page shows exactly which subjects are rising. Ready?" },
];

/**
 * First-run guided tour. Shows only for an account that has answered nothing yet, and only
 * until it's been completed or skipped on this device — after that it never returns.
 */
export default function Tour() {
  const router = useRouter();
  const { stats } = useAppData();
  // Derived, not effect-driven: on the server (and if storage is unavailable) this reads as
  // dismissed, and stats are null during hydration — so first paint is identical everywhere,
  // and the tour appears only once the account's zero-answers state is actually known.
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return true;
    try { return !!localStorage.getItem(DONE_KEY); } catch { return true; }
  });
  const [i, setI] = useState(0);
  const open = !dismissed && !!stats && stats.questions_answered === 0;

  const dismiss = () => {
    try { localStorage.setItem(DONE_KEY, "1"); } catch { /* best effort */ }
    setDismissed(true);
  };
  const finish = () => {
    dismiss();
    router.push("/daily");
  };

  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/50 px-5"
          role="dialog" aria-modal="true" aria-label="Welcome tour"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <motion.div className="card card-2 w-full max-w-sm overflow-hidden p-6 text-center"
            initial={{ scale: 0.94, y: 12, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ opacity: 0, scale: 0.96 }} transition={{ type: "spring", visualDuration: 0.35, bounce: 0.2 }}>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div key={i}
                initial={{ opacity: 0, x: 34 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -34 }}
                transition={{ type: "spring", visualDuration: 0.3, bounce: 0 }}>
                <div className="flex justify-center"><Mascot mood={step.mood} trigger={i} size={110} /></div>
                <div className={`mx-auto mt-2 grid h-9 w-9 place-items-center rounded-xl ${step.tint}`}>
                  <step.icon size={17} />
                </div>
                <h2 className="mt-3 text-xl font-extrabold">{step.title}</h2>
                <p className="pretty mt-2 text-sm font-semibold leading-relaxed text-ink-soft">{step.body}</p>
              </motion.div>
            </AnimatePresence>

            {/* progress dots */}
            <div className="mt-5 flex items-center justify-center gap-1.5" aria-hidden>
              {STEPS.map((_, d) => (
                <span key={d} className={`h-1.5 rounded-full transition-all duration-300 ${d === i ? "w-5 bg-primary" : "w-1.5 bg-line-strong"}`} />
              ))}
            </div>

            <div className="mt-5 flex gap-2">
              {i > 0 && !last && (
                <button className="btn btn-ghost !min-h-11 flex-none !px-4" onClick={() => setI(i - 1)} aria-label="Previous step">←</button>
              )}
              <button className="btn btn-primary !min-h-11 flex-1" onClick={() => (last ? finish() : setI(i + 1))}>
                {last ? <>Start today&apos;s challenge <ArrowRight size={16} /></> : i === 0 ? "Show me around" : "Next"}
              </button>
            </div>
            <button className="btn btn-quiet !min-h-9 mt-1.5 w-full text-xs" onClick={dismiss}>
              {last ? "I'll explore on my own" : "Skip the tour"}
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
