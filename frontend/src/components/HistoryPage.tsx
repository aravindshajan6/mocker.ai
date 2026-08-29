"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FileClock } from "lucide-react";
import { EmptyState, Item, PageHeader, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";
import type { HistoryRow } from "@/lib/types";

const MODE_LABEL: Record<string, string> = {
  daily: "Daily challenge",
  mixed: "Mixed practice",
  topic: "Topic practice",
  review: "Review session",
  weak: "Weak-topic practice",
  exam: "Mock exam",
  "current-affairs": "Current affairs",
};

export default function HistoryPage() {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.history().then(setRows).catch((e) => setError(e?.message || "Could not load your history."));
  }, []);

  if (error) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
  if (!rows) return <SkeletonPage />;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title="History" icon={<FileClock size={20} />} subtitle="Everything you've completed, most recent first." />
      </Item>

      {rows.length === 0 ? (
        <Item>
          <EmptyState icon="🗂️" title="Nothing here yet" body="Finish a quiz and it will show up here with your score."
            action={<Link href="/" className="btn btn-primary">Start a quiz</Link>} />
        </Item>
      ) : (
        <div className="flex flex-col gap-2.5">
          {rows.map((h) => {
            const pct = h.total ? h.correct / h.total : 0;
            const href = h.mode === "exam" ? `/exam/${h.id}/result` : `/quiz/${h.id}/result`;
            return (
              <Item key={h.id}>
                <Link href={href} className="card card-interactive p-4 flex items-center gap-3.5">
                  <span className="text-2xl shrink-0">{h.topic_icon ?? (h.mode === "daily" ? "📅" : h.mode === "exam" ? "📝" : "🎯")}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-extrabold text-sm truncate">{h.topic ?? MODE_LABEL[h.mode] ?? "Practice"}</p>
                    <p className="text-xs text-muted font-semibold">
                      {h.finished_at ? new Date(h.finished_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : ""}
                      {" · "}{h.correct}/{h.total} correct
                    </p>
                    <div className="h-1 mt-1.5 rounded-full bg-surface-2 overflow-hidden max-w-[220px]">
                      <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: pct >= 0.6 ? "var(--success)" : "var(--danger)" }} />
                    </div>
                  </div>
                  <span className="text-sm font-extrabold text-primary shrink-0 tabular">+{h.score}</span>
                </Link>
              </Item>
            );
          })}
        </div>
      )}
    </Stagger>
  );
}
