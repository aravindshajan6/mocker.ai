"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2, Newspaper, RefreshCw } from "lucide-react";
import { EmptyState, ErrorNote, Item, PageHeader, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";
import type { CurrentAffairs } from "@/lib/types";

const WINDOW = 30;

export default function CurrentAffairsPage() {
  const router = useRouter();
  const [ca, setCa] = useState<CurrentAffairs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.currentAffairs(WINDOW).then(setCa).catch((e) => setError(e?.message || "Could not load current affairs."));
  }, []);

  const open = async (day: string) => {
    setBusy(day);
    setError(null);
    try {
      const s = await api.startQuiz({ mode: "current-affairs", day });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Could not open that day.");
      setBusy(null);
    }
  };

  if (error && !ca) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
  if (!ca) return <SkeletonPage />;

  const withQuestions = ca.days.filter((d) => d.count > 0);
  const done = withQuestions.filter((d) => d.finished).length;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title="Current affairs" icon={<Newspaper size={20} />}
          subtitle="Questions written each morning from the day's Indian news." />
      </Item>

      <ErrorNote message={error} />

      <Item>
        <div className="card p-4 flex items-center gap-3">
          <div className="grid place-items-center h-11 w-11 rounded-2xl bg-accent-soft text-accent-ink shrink-0">
            <RefreshCw size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-extrabold text-sm">
              {withQuestions.length} day{withQuestions.length === 1 ? "" : "s"} available · {done} completed
            </p>
            <p className="text-xs text-muted font-semibold">
              A new set lands every morning. Older days stay here — doing them counts towards today&apos;s
              practice, though it won&apos;t restore a streak you already lost.
            </p>
          </div>
        </div>
      </Item>

      {withQuestions.length === 0 ? (
        <Item>
          <EmptyState icon="📰" title="No news questions yet"
            body="The generator runs each morning. Once it has run, the day's questions appear here." />
        </Item>
      ) : (
        <div className="flex flex-col gap-2.5">
          {withQuestions.map((d) => {
            const date = new Date(d.day + "T00:00:00");
            const isToday = d.day === ca.today;
            const progress = d.count ? d.answered / d.count : 0;
            return (
              <Item key={d.day}>
                <button onClick={() => open(d.day)} disabled={busy !== null}
                  className="card card-interactive p-4 w-full text-left flex items-center gap-3.5 disabled:opacity-60">
                  <div className={`shrink-0 grid place-items-center h-12 w-12 rounded-2xl font-extrabold leading-none
                    ${d.finished ? "bg-success-soft text-success" : isToday ? "bg-accent-soft text-accent-ink" : "bg-surface-2 text-ink-soft"}`}>
                    <span className="text-lg">{date.getDate()}</span>
                    <span className="text-[9px] uppercase tracking-wide">{date.toLocaleDateString(undefined, { month: "short" })}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-extrabold text-sm">
                      {isToday ? "Today" : date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
                    </p>
                    <p className="text-xs text-muted font-semibold">
                      {d.finished
                        ? `Completed · ${d.score} points`
                        : d.answered > 0
                          ? `${d.answered} of ${d.count} answered`
                          : `${d.count} question${d.count === 1 ? "" : "s"}`}
                    </p>
                    {!d.finished && d.answered > 0 && (
                      <div className="h-1 mt-1.5 rounded-full bg-surface-2 overflow-hidden">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${progress * 100}%` }} />
                      </div>
                    )}
                  </div>
                  {d.finished
                    ? <CheckCircle2 size={20} className="text-success shrink-0" />
                    : <span className="text-sm font-extrabold text-primary shrink-0">{busy === d.day ? "…" : "Start"}</span>}
                </button>
              </Item>
            );
          })}
        </div>
      )}

      {!ca.has_key && (
        <Item>
          <p className="text-[11px] text-muted font-semibold text-center">
            Running in basic mode — add an LLM key in .env for richer questions.
          </p>
        </Item>
      )}
    </Stagger>
  );
}
