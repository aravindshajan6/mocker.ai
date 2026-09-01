"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, CalendarCheck, Flame, Newspaper, RotateCcw, Sparkles, Timer, TrendingUp } from "lucide-react";
import Mascot, { type Mood } from "@/components/Mascot";
import { useAppData } from "@/components/AppData";
import Tour from "@/components/Tour";
import { Chip, Item, Num, ProgressRing, SectionTitle, SkeletonPage, Stagger } from "@/components/ui";
import { api, greeting } from "@/lib/api";

const NUDGES = [
  "One quiz a day keeps the exam fear away.",
  "Small steps every day add up to big scores.",
  "You don't have to be perfect — just show up.",
  "Every question you answer is one less surprise on exam day.",
  "Consistency beats cramming. Let's do a few.",
];

export default function Home() {
  const router = useRouter();
  const { user, stats, daily, due, ca, topics, loading, error, refresh } = useAppData();
  const [starting, setStarting] = useState<string | null>(null);

  const start = async (mode: "daily" | "mixed" | "review" | "current-affairs", day?: string) => {
    setStarting(mode);
    try {
      const s = await api.startQuiz({ mode, day });
      router.push(`/quiz/${s.id}`);
    } catch {
      setStarting(null);
      void refresh();
    }
  };

  if (error) return (
    <div className="mt-16 text-center flex flex-col items-center gap-3">
      <Mascot mood="oops" size={110} />
      <p className="text-danger font-bold">{error}</p>
      <button className="btn btn-ghost" onClick={() => location.reload()}>Try again</button>
    </div>
  );
  if (loading || !user || !stats || !daily) return <SkeletonPage />;

  const firstName = user.name.split(" ")[0];
  const mood: Mood = stats.daily_done_today ? "happy" : stats.current_streak === 0 && stats.questions_answered > 0 ? "sleepy" : "wave";
  const nudge = NUDGES[new Date().getDate() % NUDGES.length];
  const caToday = ca?.days[0];
  const started = topics.reduce((n, t) => n + t.answered, 0);
  const total = topics.reduce((n, t) => n + t.question_count, 0);

  return (
    <>
    <Tour />
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <div className="flex items-center gap-3">
          <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 18 }}>
            <Mascot mood={mood} size={92} />
          </motion.div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-extrabold leading-tight tracking-tight">{greeting()}, {firstName}</h1>
            <p className="text-muted font-semibold text-sm mt-0.5">
              {stats.daily_done_today ? "Today’s challenge is done. Fancy a bit more?" : nudge}
            </p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              <Chip tone="accent"><Flame size={12} /> <Num value={stats.current_streak} /> day streak</Chip>
              <Chip tone="primary"><Sparkles size={12} /> <Num value={stats.total_points} /> pts · {stats.level_title}</Chip>
            </div>
          </div>
        </div>
      </Item>

      {/* Daily challenge hero */}
      <Item>
        <div className="card-hero p-5">
          <div className="relative flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-extrabold uppercase tracking-[0.14em] opacity-80">Today’s challenge</p>
              <h2 className="text-2xl font-extrabold mt-1 leading-tight">{daily.size} questions, all topics</h2>
              <p className="text-sm font-semibold opacity-90 mt-1 max-w-sm">
                {daily.done
                  ? `Done — you scored ${daily.score} points (${daily.correct}/${daily.size} correct).`
                  : "The same set for everyone today. Finish it to keep your streak and earn a +25 bonus."}
              </p>
            </div>
            <ProgressRing value={daily.done ? 1 : 0} size={62} stroke={6} color="rgba(255,255,255,.95)">
              <CalendarCheck size={22} className="text-white" />
            </ProgressRing>
          </div>
          <button className="relative btn w-full mt-4 bg-white/95 text-[#12463c] hover:bg-white"
            onClick={() => start(daily.done ? "mixed" : "daily")} disabled={starting !== null}>
            {starting ? "Getting ready…" : daily.done ? "One more round" : daily.session_id ? "Continue today’s challenge" : "Start today’s challenge"}
            <ArrowRight size={17} />
          </button>
        </div>
      </Item>

      {/* Quick actions */}
      <Item>
        <div className="grid grid-cols-2 gap-3">
          <ActionCard href="/exam" icon={<Timer size={18} />} title="Exam mode"
            body="100 questions, 75 min, negative marking" tone="info" />
          <ActionCard href="/current-affairs" icon={<Newspaper size={18} />} title="Current affairs"
            body={caToday?.count ? `${caToday.count} from today’s news` : "Fresh each morning"} tone="accent"
            badge={caToday && !caToday.finished && caToday.count > 0 ? "New" : undefined} />
        </div>
      </Item>

      {/* Review queue */}
      {due && (due.due_now > 0 || due.due_today > 0) && (
        <Item>
          <div className={`card p-4 flex items-center gap-3 ${due.due_now > 0 ? "border-accent/40" : ""}`}>
            <div className="grid place-items-center h-11 w-11 rounded-2xl bg-accent-soft text-accent-ink shrink-0">
              <RotateCcw size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-extrabold text-sm">
                {due.due_now > 0
                  ? `${due.due_now} question${due.due_now === 1 ? "" : "s"} ready to revise`
                  : `${due.due_today} coming back later today`}
              </p>
              <p className="text-xs text-muted font-semibold">
                {due.due_now > 0
                  ? "Timed to reach you just before you’d forget them."
                  : "Spaced repetition is holding these until they're worth repeating."}
                {due.retention !== null ? ` ${Math.round(due.retention * 100)}% retention.` : ""}
              </p>
            </div>
            {due.due_now > 0 && (
              <button className="btn btn-ghost !min-h-10 px-4 text-sm shrink-0" onClick={() => start("review")} disabled={starting !== null}>
                Revise
              </button>
            )}
          </div>
        </Item>
      )}

      {/* Level */}
      <Item>
        <div className="card p-4 flex items-center gap-4">
          <ProgressRing value={stats.level_progress} size={64} stroke={6}>
            <span className="text-sm font-extrabold">{stats.level}</span>
          </ProgressRing>
          <div className="flex-1 min-w-0">
            <p className="font-extrabold">{stats.level_title}</p>
            <p className="text-xs text-muted font-semibold mt-0.5">
              <Num value={stats.points_to_next_level} /> points to the next level
            </p>
            <p className="text-xs text-muted font-semibold">
              {started.toLocaleString()} of {total.toLocaleString()} questions seen
            </p>
          </div>
          <Link href="/progress" className="btn btn-quiet !min-h-9 text-xs shrink-0">
            <TrendingUp size={15} /> Progress
          </Link>
        </div>
      </Item>

      {/* Topics preview */}
      <Item>
        <SectionTitle action={<Link href="/practice" className="text-sm font-extrabold text-primary">All topics →</Link>}>
          Practise by topic
        </SectionTitle>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {topics.slice(0, 6).map((t) => (
            <Link key={t.slug} href={`/practice/${t.slug}`} className="card card-interactive p-3.5 flex flex-col gap-1.5">
              <span className="text-xl">{t.icon}</span>
              <span className="font-extrabold text-sm leading-tight">{t.name}</span>
              <span className="text-[11px] text-muted font-semibold">
                {t.answered}/{t.question_count}{t.accuracy !== null ? ` · ${Math.round(t.accuracy * 100)}%` : ""}
              </span>
            </Link>
          ))}
        </div>
      </Item>
    </Stagger>
  </>
  );
}

function ActionCard({ href, icon, title, body, tone, badge }:
  { href: string; icon: React.ReactNode; title: string; body: string; tone: "info" | "accent"; badge?: string }) {
  const bg = tone === "info" ? "bg-info-soft text-info" : "bg-accent-soft text-accent-ink";
  return (
    <Link href={href} className="card card-interactive p-4 flex flex-col gap-2 relative">
      {badge && (
        <span className="absolute top-3 right-3 rounded-full bg-accent text-accent-ink text-[10px] font-extrabold px-2 py-0.5 pulse-ring">
          {badge}
        </span>
      )}
      <div className={`grid place-items-center h-10 w-10 rounded-2xl ${bg}`}>{icon}</div>
      <p className="font-extrabold text-sm leading-tight">{title}</p>
      <p className="text-[11px] text-muted font-semibold leading-snug">{body}</p>
    </Link>
  );
}
