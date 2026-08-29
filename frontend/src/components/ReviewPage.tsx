"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Brain, RotateCcw } from "lucide-react";
import Mascot from "@/components/Mascot";
import { useAppData } from "@/components/AppData";
import { EmptyState, ErrorNote, Item, Num, PageHeader, ProgressRing, SkeletonPage, Stagger, StatTile } from "@/components/ui";
import { api } from "@/lib/api";

export default function ReviewPage() {
  const router = useRouter();
  const { due, loading } = useAppData();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await api.startQuiz({ mode: "review", count: 15 });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Nothing is due right now.");
      setBusy(false);
    }
  };

  if (loading || !due) return <SkeletonPage />;

  const ready = due.due_now > 0;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title="Review" icon={<RotateCcw size={20} />}
          subtitle="Questions come back just before you would have forgotten them." />
      </Item>

      <ErrorNote message={error} />

      {due.learning === 0 ? (
        <Item>
          <EmptyState icon="🌱" title="Nothing to review yet"
            body="Answer some questions and they'll start appearing here, scheduled so you meet them again at the moment repetition pays off." />
        </Item>
      ) : (
        <>
          <Item>
            <div className="card p-5 flex items-center gap-4">
              <ProgressRing value={due.learning ? due.due_now / Math.max(due.learning, 1) : 0} size={84}
                color={ready ? "var(--accent)" : "var(--primary)"}>
                <div className="text-center leading-none">
                  <div className="text-xl font-extrabold"><Num value={due.due_now} /></div>
                  <div className="text-[9px] font-extrabold text-muted mt-0.5">DUE</div>
                </div>
              </ProgressRing>
              <div className="flex-1 min-w-0">
                <p className="font-extrabold">
                  {ready ? "Ready when you are" : "Nothing due this minute"}
                </p>
                <p className="text-sm text-muted font-semibold mt-0.5">
                  {ready
                    ? `${due.due_now} question${due.due_now === 1 ? "" : "s"} have come around again.`
                    : due.due_today > 0
                      ? `${due.due_today} will come back later today.`
                      : "You're all caught up. New reviews appear as you practise."}
                </p>
                <button className="btn btn-primary mt-3 w-full sm:w-auto" onClick={start} disabled={!ready || busy}>
                  {busy ? "Building your set…" : ready ? "Start reviewing" : "Nothing due"}
                </button>
              </div>
            </div>
          </Item>

          <Item>
            <div className="grid grid-cols-3 gap-3">
              <StatTile label="In rotation" value={<Num value={due.learning} />} sub="questions tracked" />
              <StatTile label="Due today" value={<Num value={due.due_today} />} />
              <StatTile label="Retention" value={due.retention !== null ? `${Math.round(due.retention * 100)}%` : "—"}
                sub={due.retention !== null ? "on repeat encounters" : "needs more data"} />
            </div>
          </Item>
        </>
      )}

      <Item>
        <div className="card p-4 flex gap-3">
          <div className="grid place-items-center h-10 w-10 rounded-2xl bg-info-soft text-info shrink-0">
            <Brain size={18} />
          </div>
          <div>
            <p className="font-extrabold text-sm">How the timing works</p>
            <p className="text-xs text-muted font-semibold leading-relaxed mt-0.5">
              Every answer you give schedules that question&apos;s next appearance using FSRS. Get it wrong and it
              returns within minutes; get it right repeatedly and the gap stretches to days, then weeks. You
              never have to manage this — it builds itself from ordinary practice.
            </p>
          </div>
        </div>
      </Item>

      <Item>
        <div className="flex justify-center pt-2 opacity-80">
          <Mascot mood={ready ? "think" : "happy"} size={92} />
        </div>
      </Item>
    </Stagger>
  );
}
