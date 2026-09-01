"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, BrainCircuit, CalendarCheck, Flame, Timer, TrendingUp } from "lucide-react";
import Mascot, { type Mood } from "@/components/Mascot";
import { useAppData } from "@/components/AppData";

const DONE_KEY = "mocker:tour-done";
const TOUR_EVENT = "mocker:start-tour";

/** Replays the tour from anywhere (e.g. the nav's "Take the tour" button). */
export function startTour() {
  window.dispatchEvent(new Event(TOUR_EVENT));
}

/* Each step opens the real page it talks about, and the card parks itself in a corner where it
   covers the least: alternating top/bottom on desktop, docked above the tab bar on mobile. */
const STEPS: {
  route: string; pos: string; mood: Mood; icon: typeof Flame; tint: string; title: string; body: string;
}[] = [
  { route: "/", pos: "lg:right-6 lg:top-auto lg:bottom-6", mood: "wave", icon: CalendarCheck, tint: "bg-primary-soft text-primary",
    title: "Hi, I'm Kunju!",
    body: "Welcome to Mocker — your calm corner for PSC, SSC and UPSC prep. This is Home: today's challenge, quick actions, your topics. Let me walk you through the real pages." },
  { route: "/daily", pos: "lg:right-6 lg:top-20 lg:bottom-auto", mood: "happy", icon: Flame, tint: "bg-accent-soft text-accent-ink",
    title: "The daily challenge",
    body: "This page refreshes every morning with a set shared by every aspirant, so scores really compare. Finish it to grow a streak — miss a day and I repair it, twice a month." },
  { route: "/practice", pos: "lg:right-6 lg:top-auto lg:bottom-6", mood: "think", icon: BrainCircuit, tint: "bg-primary-soft text-primary",
    title: "Practise any subject",
    body: "Every bank from Indian History to General English lives here — or let me build sets from the topics costing you marks. Struggled questions return for revision right before you'd forget them." },
  { route: "/exam", pos: "lg:right-6 lg:top-20 lg:bottom-auto", mood: "oops", icon: Timer, tint: "bg-info-soft text-info",
    title: "Rehearse the real exam",
    body: "Full-length timed papers with the hall's own rules — negative marking, a question palette, deliberate blanks. Better to meet them here than there." },
  { route: "/progress", pos: "lg:right-6 lg:top-auto lg:bottom-6", mood: "celebrate", icon: TrendingUp, tint: "bg-accent-soft text-accent-ink",
    title: "Watch yourself improve",
    body: "Points, levels, badges, a weekly leaderboard, and per-subject trends — this page keeps an honest score of your consistency. Ready for your first set?" },
];

/**
 * First-run guided walkthrough. Non-modal on purpose: no scrim, the page stays live behind a
 * compact card, so each step genuinely shows the screen it describes. Appears only for an
 * account that has answered nothing, until completed or skipped on this device.
 */
export default function Tour() {
  const router = useRouter();
  const pathname = usePathname();
  const { stats } = useAppData();
  // Derived, not effect-driven: on the server (and if storage is unavailable) this reads as
  // dismissed, and stats are null during hydration — so first paint is identical everywhere.
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return true;
    try { return !!localStorage.getItem(DONE_KEY); } catch { return true; }
  });
  const [i, setI] = useState(0);
  // A manual replay overrides both the storage flag and the new-account gate.
  const [forced, setForced] = useState(false);
  const open = forced || (!dismissed && !!stats && stats.questions_answered === 0);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  useEffect(() => {
    const onStart = () => { setI(0); setForced(true); };
    window.addEventListener(TOUR_EVENT, onStart);
    return () => window.removeEventListener(TOUR_EVENT, onStart);
  }, []);

  // Take the user to the page the current step describes.
  useEffect(() => {
    if (open && pathname !== step.route) router.push(step.route);
    // pathname is deliberately not a dependency: if the user wanders off mid-step, the tour
    // waits where it is rather than yanking them back.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, i]);

  const dismiss = () => {
    try { localStorage.setItem(DONE_KEY, "1"); } catch { /* best effort */ }
    setDismissed(true);
    setForced(false);
  };
  const finish = () => {
    dismiss();
    router.push("/daily");
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          layout
          role="dialog" aria-label="Welcome tour"
          className={`fixed inset-x-3 bottom-20 z-50 lg:inset-x-auto lg:w-[320px] ${step.pos}`}
          transition={{ type: "spring", visualDuration: 0.45, bounce: 0.15 }}
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}>
          <div className="card border-primary-line p-4" style={{ boxShadow: "var(--shadow-3)" }}>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div key={i}
                initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}
                transition={{ type: "spring", visualDuration: 0.28, bounce: 0 }}>
                <div className="flex items-start gap-3">
                  <Mascot mood={step.mood} trigger={i} size={64} className="shrink-0" />
                  <div className="min-w-0">
                    <div className={`mb-1.5 grid h-7 w-7 place-items-center rounded-lg ${step.tint}`}>
                      <step.icon size={14} />
                    </div>
                    <h2 className="font-extrabold leading-tight">{step.title}</h2>
                  </div>
                </div>
                <p className="pretty mt-2 text-[13px] font-semibold leading-relaxed text-ink-soft">{step.body}</p>
              </motion.div>
            </AnimatePresence>

            <div className="mt-3 flex items-center gap-1.5" aria-hidden>
              {STEPS.map((_, d) => (
                <span key={d} className={`h-1.5 rounded-full transition-all duration-300 ${d === i ? "w-5 bg-primary" : "w-1.5 bg-line-strong"}`} />
              ))}
              <button className="ml-auto text-[11px] font-extrabold text-muted transition hover:text-ink" onClick={dismiss}>
                {last ? "Explore on my own" : "Skip tour"}
              </button>
            </div>

            <div className="mt-3 flex gap-2">
              {i > 0 && (
                <button className="btn btn-ghost !min-h-10 flex-none !px-3.5 text-sm" onClick={() => setI(i - 1)} aria-label="Previous step">←</button>
              )}
              <button className="btn btn-primary !min-h-10 flex-1 text-sm" onClick={() => (last ? finish() : setI(i + 1))}>
                {last ? <>Start today&apos;s challenge <ArrowRight size={15} /></> : i === 0 ? "Show me around" : "Next"}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
