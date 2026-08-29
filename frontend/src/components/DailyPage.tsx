"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CalendarCheck, Flame, Trophy } from "lucide-react";
import Mascot from "@/components/Mascot";
import { useAppData } from "@/components/AppData";
import { ErrorNote, Item, Num, PageHeader, ProgressRing, SkeletonPage, Stagger, StatTile } from "@/components/ui";
import { api } from "@/lib/api";

export default function DailyPage() {
  const router = useRouter();
  const { daily, stats, loading } = useAppData();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await api.startQuiz({ mode: "daily" });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Could not start today's challenge.");
      setBusy(false);
    }
  };

  if (loading || !daily || !stats) return <SkeletonPage />;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title="Daily challenge" icon={<CalendarCheck size={20} />}
          subtitle="Ten questions across every topic. The same set for everyone, every day." />
      </Item>

      <ErrorNote message={error} />

      <Item>
        <div className="card-hero p-6 text-center">
          <div className="relative flex flex-col items-center gap-2">
            <Mascot mood={daily.done ? "celebrate" : "wave"} size={104} />
            {daily.done ? (
              <>
                <h2 className="text-2xl font-extrabold">Done for today</h2>
                <p className="font-semibold opacity-90">
                  {daily.correct}/{daily.size} correct · {daily.score} points
                </p>
              </>
            ) : (
              <>
                <h2 className="text-2xl font-extrabold">{daily.size} questions are waiting</h2>
                <p className="font-semibold opacity-90 max-w-sm">
                  Finish to keep your streak alive and collect a +25 bonus.
                </p>
              </>
            )}
            <button className="btn w-full max-w-xs mt-3 bg-white/95 text-[#12463c] hover:bg-white"
              onClick={go} disabled={busy || daily.done}>
              {busy ? "Getting ready…" : daily.done ? "Completed" : daily.session_id ? "Continue" : "Start now"}
            </button>
          </div>
        </div>
      </Item>

      <Item>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Streak" value={<><Flame size={16} className="inline text-accent" /> <Num value={stats.current_streak} /></>}
            sub={stats.next_milestone ? `${stats.next_milestone - stats.current_streak} to ${stats.next_milestone}` : `best ${stats.longest_streak}`} />
          <StatTile label="Repairs left" value={<Num value={stats.repairs_left} />} sub="this month" />
          <StatTile label="Points" value={<Num value={stats.total_points} />} sub={stats.level_title} />
        </div>
      </Item>

      <Item>
        <div className="card p-4 flex items-center gap-4">
          <ProgressRing value={stats.level_progress} size={64} stroke={6} color="var(--accent)">
            <Trophy size={20} className="text-accent" />
          </ProgressRing>
          <div className="flex-1">
            <p className="font-extrabold text-sm">Level {stats.level} · {stats.level_title}</p>
            <p className="text-xs text-muted font-semibold mt-0.5">
              <Num value={stats.points_to_next_level} /> points to go
            </p>
          </div>
        </div>
      </Item>

      <Item>
        <div className="card p-4">
          <p className="font-extrabold text-sm mb-1">How the daily set is built</p>
          <p className="text-xs text-muted font-semibold leading-relaxed">
            Seven questions are the same for every learner, so scores are comparable. Up to three slots are
            given over to questions <i>you</i> are due to revise, and a few fresh current-affairs questions
            are mixed in when they are available.
          </p>
        </div>
      </Item>
    </Stagger>
  );
}
