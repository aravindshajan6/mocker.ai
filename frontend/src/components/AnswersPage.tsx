"use client";

import { useCallback, useEffect, useState } from "react";
import { BookMarked, ChevronLeft } from "lucide-react";
import AnsweredCard from "@/components/AnsweredCard";
import { EmptyState, ErrorNote, Item, PageHeader, ProgressBar, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";
import type { Answers } from "@/lib/types";

type Only = "all" | "wrong" | "correct";
const PAGE = 25;

export default function AnswersPage() {
  const [data, setData] = useState<Answers | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [only, setOnly] = useState<Only>("all");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (t: string | null, o: Only, off: number, showSpinner = true) => {
    if (showSpinner) setLoading(true);
    try {
      setData(await api.answers({ topic: t ?? undefined, only: o, limit: PAGE, offset: off }));
      setError(null);
    } catch (e) {
      setError((e as Error)?.message || "Could not load your answers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Deferred so the effect body does not write state synchronously on mount.
    const id = setTimeout(() => void load(null, "all", 0, false), 0);
    return () => clearTimeout(id);
  }, [load]);

  const choose = (t: string | null) => { setTopic(t); setOffset(0); void load(t, only, 0); };
  const setFilter = (o: Only) => { setOnly(o); setOffset(0); void load(topic, o, 0); };
  const page = (off: number) => { setOffset(off); void load(topic, only, off); window.scrollTo({ top: 0, behavior: "smooth" }); };

  if (!data && !error) return <SkeletonPage />;

  const current = data?.topics.find((t) => t.slug === topic);
  const totalAttempted = data?.topics.reduce((n, t) => n + t.attempted, 0) ?? 0;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title={current ? current.name : "My answers"} icon={<BookMarked size={20} />}
          subtitle={current
            ? `${current.attempted} answered · ${current.correct} right, ${current.wrong} wrong`
            : "Every question you've attempted, grouped by subject."} />
      </Item>

      <ErrorNote message={error} />

      {topic && (
        <Item>
          <button onClick={() => choose(null)} className="inline-flex items-center gap-1.5 text-sm font-extrabold text-muted hover:text-ink">
            <ChevronLeft size={16} /> All subjects
          </button>
        </Item>
      )}

      {!topic && (data?.topics.length ?? 0) === 0 ? (
        <Item>
          <EmptyState icon="📖" title="Nothing to review yet"
            body="Answer some questions and they'll collect here by subject, so you can come back and go over them." />
        </Item>
      ) : !topic ? (
        <>
          <Item>
            <p className="text-sm font-semibold text-muted">{totalAttempted} questions answered across {data?.topics.length} subjects.</p>
          </Item>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data?.topics.map((t) => {
              const acc = t.attempted ? t.correct / t.attempted : 0;
              return (
                <Item key={t.slug}>
                  <button onClick={() => choose(t.slug)} className="card card-interactive p-4 w-full text-left flex gap-3.5">
                    <span className="text-2xl shrink-0">{t.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-extrabold leading-tight">{t.name}</p>
                      <p className="text-xs text-muted font-semibold mt-0.5">
                        {t.attempted} answered · {t.wrong} to revisit
                      </p>
                      <ProgressBar value={acc} className="!h-1.5 mt-2"
                        color={acc >= 0.6 ? "var(--success)" : "var(--danger)"} />
                    </div>
                    <span className="text-sm font-extrabold text-muted shrink-0 self-center">{Math.round(acc * 100)}%</span>
                  </button>
                </Item>
              );
            })}
          </div>
        </>
      ) : (
        <>
          <Item>
            <div className="flex gap-1.5">
              {([["all", "All"], ["wrong", "Got wrong"], ["correct", "Got right"]] as const).map(([f, label]) => (
                <button key={f} onClick={() => setFilter(f as Only)}
                  className={`text-xs font-extrabold px-3 py-1.5 rounded-xl transition ${only === f ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted hover:text-ink"}`}>
                  {label}
                </button>
              ))}
            </div>
          </Item>

          {data && data.questions.length === 0 ? (
            <Item><p className="text-center text-muted font-semibold py-8">Nothing in this filter.</p></Item>
          ) : (
            data?.questions.map((q) => <Item key={q.question_id}><AnsweredCard q={q} /></Item>)
          )}

          {data && data.total > PAGE && (
            <Item>
              <div className="flex items-center justify-between">
                <button className="btn btn-ghost !min-h-10 text-sm" disabled={offset === 0 || loading}
                  onClick={() => page(Math.max(0, offset - PAGE))}>← Previous</button>
                <span className="text-xs font-extrabold text-muted">
                  {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
                </span>
                <button className="btn btn-ghost !min-h-10 text-sm" disabled={offset + PAGE >= data.total || loading}
                  onClick={() => page(offset + PAGE)}>Next →</button>
              </div>
            </Item>
          )}
        </>
      )}
    </Stagger>
  );
}
