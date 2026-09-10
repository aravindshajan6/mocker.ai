"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowLeft, ArrowRight, ArrowUpRight, BarChart3, ShieldCheck } from "lucide-react";
import { useAppData } from "@/components/AppData";
import { ErrorNote, SkeletonCard } from "@/components/ui";
import { api } from "@/lib/api";
import type { AnalyticsDashboard as Data } from "@/lib/types";
import {
  CategoryBars, ChartCard, CONTEXT, fmtDay, fmtDuration, fmtPct, HBars, heatStep, HourHeatmap, Legend,
  Sparkline, TimeChart, WEEKDAYS,
} from "./charts";

const RANGES = [7, 30, 90] as const;
type Range = (typeof RANGES)[number];

const MODE_LABEL: Record<string, string> = {
  daily: "Daily challenge", topic: "Topic practice", mixed: "Mixed practice", weak: "Weak topics",
  review: "Revision", retry: "Retry wrong answers", "current-affairs": "Current affairs", exam: "Exam mode",
};
const SOURCE_LABEL: Record<string, string> = {
  seed: "Hand-authored", milu: "MILU dataset", pyq: "Kerala PSC past papers", news: "Current affairs (AI)",
  "news-heuristic": "Current affairs (rules)", admin: "Added by admin",
};
const DIFFICULTY = ["Easy", "Medium", "Hard"];
/** Accuracy from fewer answers than this is shown but not ranked — three answers is noise. */
const MIN_SAMPLE = 10;
const SMALL_NOTE = `Grey: fewer than ${MIN_SAMPLE} answers — too few to rank`;

/** Rank by accuracy (hardest first) only where the sample means something; small ones go last, greyed. */
function rankAccuracy<T extends { answers: number; correct: number }>(items: T[], label: (t: T) => string, icon?: (t: T) => string) {
  const rows = items.filter((t) => t.answers > 0).map((t) => ({
    label: label(t), icon: icon?.(t), value: t.correct / t.answers,
    detail: `${t.answers.toLocaleString()} answer${t.answers === 1 ? "" : "s"}`, muted: t.answers < MIN_SAMPLE,
  }));
  return [...rows.filter((r) => !r.muted).sort((a, b) => a.value - b.value), ...rows.filter((r) => r.muted)];
}

/* ---------------------------------------------------------------- helpers ---- */

/** Trailing 7-day mean — the signal under a noisy daily count. */
function rolling(values: number[], window = 7): number[] {
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - window + 1), i + 1);
    return +(slice.reduce((a, b) => a + b, 0) / slice.length).toFixed(2);
  });
}

type Delta = { text: string; dir: "up" | "down" | "flat" } | null;

function delta(cur: number | null, prev: number | null, kind: "count" | "ratio" = "count"): Delta {
  if (cur === null || prev === null) return null;
  if (kind === "ratio") {
    const pts = (cur - prev) * 100;
    if (Math.abs(pts) < 0.5) return { text: "no change", dir: "flat" };
    return { text: `${pts > 0 ? "+" : "−"}${Math.abs(pts).toFixed(1)} pts`, dir: pts > 0 ? "up" : "down" };
  }
  if (prev === 0) return cur > 0 ? { text: "new this period", dir: "up" } : { text: "no change", dir: "flat" };
  const pct = ((cur - prev) / prev) * 100;
  if (Math.abs(pct) < 0.5) return { text: "no change", dir: "flat" };
  return { text: `${pct > 0 ? "+" : "−"}${Math.abs(pct).toFixed(0)}%`, dir: pct > 0 ? "up" : "down" };
}

/* ------------------------------------------------------------------ tiles ---- */

function Kpi({ label, value, d, spark, range }: {
  label: string; value: string; d: Delta; spark?: number[]; range: number;
}) {
  // Every KPI here is better going up, so direction and good/bad agree; the arrow and words carry
  // the meaning, the colour only reinforces it.
  const tone = d?.dir === "up" ? "text-success" : d?.dir === "down" ? "text-danger" : "text-muted";
  const Icon = d?.dir === "up" ? ArrowUpRight : d?.dir === "down" ? ArrowDownRight : null;
  return (
    <div className="card p-4 flex flex-col">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted">{label}</p>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <p className="text-[26px] font-extrabold leading-none whitespace-nowrap">{value}</p>
        {spark && <Sparkline values={spark} width={64} />}
      </div>
      <p className="mt-2 flex items-center gap-1 text-[11px] whitespace-nowrap">
        <span className={`inline-flex items-center gap-0.5 font-extrabold ${tone}`}>
          {Icon && <Icon size={13} strokeWidth={2.6} />}{d ? d.text : "—"}
        </span>
        <span className="font-semibold text-muted">vs prior {range}d</span>
      </p>
    </div>
  );
}

function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[26px] font-extrabold leading-none">{fmtPct(value)}</span>
        <span className="text-[11px] font-bold text-muted">{label}</span>
      </div>
      {/* Track is a lighter step of the fill's own hue, so the whole bar reads as one scale. */}
      <div className="mt-2 h-2.5 rounded-full" style={{ background: "var(--primary-soft)" }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, value * 100)}%`, background: "var(--primary)" }} />
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-t border-line py-2.5">
      <span className="text-[12px] font-semibold text-ink-soft">{label}</span>
      <span className="text-[15px] font-extrabold tabular-nums">{value}</span>
    </div>
  );
}

/* ---------------------------------------------------------------- cohorts ---- */

const HEAT_FILL = ["var(--surface-2)", "var(--heat-1)", "var(--heat-2)", "var(--heat-3)", "var(--heat-4)"];

function Cohorts({ rows }: { rows: Data["cohorts"] }) {
  if (!rows.length) return <p className="text-sm text-muted font-semibold py-6 text-center">No sign-ups in the last eight weeks.</p>;
  const cols = Math.max(...rows.map((r) => r.retention.length));
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr className="text-[10px] font-extrabold uppercase tracking-wider text-muted">
            <th className="text-left font-extrabold pb-1 pr-2">Joined week of</th>
            <th className="text-right font-extrabold pb-1 pr-2">Learners</th>
            {Array.from({ length: cols }, (_, k) => <th key={k} className="font-extrabold pb-1">Wk {k}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.week}>
              <td className="text-[12px] font-bold text-ink-soft pr-2 whitespace-nowrap">{fmtDay(r.week)}</td>
              <td className="text-[12px] font-extrabold text-right pr-2 tabular-nums">{r.size}</td>
              {Array.from({ length: cols }, (_, k) => {
                const v = r.retention[k];
                if (v === undefined) return <td key={k} />;
                const step = heatStep(v);
                return (
                  <td key={k} className="h-8 min-w-12 rounded-md text-center text-[11px] font-extrabold tabular-nums"
                    title={`${fmtPct(v)} of the ${fmtDay(r.week)} cohort active in week ${k}`}
                    style={{
                      background: HEAT_FILL[step],
                      // Text on the two darkest steps takes the colour built for text on primary.
                      color: step >= 3 ? "var(--primary-ink)" : "var(--ink)",
                    }}>
                    {fmtPct(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------- page ---- */

export default function AnalyticsDashboard() {
  const { user, loading: userLoading } = useAppData();
  const [range, setRange] = useState<Range>(30);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.adminDashboard(range)
      .then((d) => { if (alive) setData(d); })
      .catch((e: Error) => { if (alive) setError(e?.message || "Could not load analytics."); });
    return () => { alive = false; };
  }, [range]);

  const derived = useMemo(() => {
    if (!data) return null;
    const s = data.current.series;
    const days = s.map((r) => r.day);
    const overall = data.current.totals.accuracy;
    const topicAcc = rankAccuracy(data.topics, (t) => t.name, (t) => t.icon);
    const weekday = WEEKDAYS.map((d) => data.heatmap.filter((c) => c.dow === d.dow).reduce((a, c) => a + c.answers, 0));
    return {
      days,
      active: s.map((r) => r.active),
      activeAvg: rolling(s.map((r) => r.active)),
      screen: s.map((r) => r.screen_seconds),
      answers: s.map((r) => r.answers),
      accuracy: s.map((r) => (r.answers ? r.correct / r.answers : null)),
      overall, topicAcc, weekday,
      busiestDay: weekday.indexOf(Math.max(...weekday)),
      spark: (key: "active" | "screen_seconds" | "answers" | "new_users") => {
        const v = s.map((r) => r[key]);
        const step = Math.max(1, Math.floor(v.length / 12));
        return v.filter((_, k) => k % step === 0 || k === v.length - 1);
      },
    };
  }, [data]);

  if (userLoading) return <div className="pt-6"><SkeletonCard lines={5} /></div>;
  if (user && !user.is_admin) {
    return (
      <div className="pt-16 text-center flex flex-col items-center gap-2">
        <ShieldCheck size={36} className="text-muted" />
        <p className="font-extrabold">Administrators only</p>
      </div>
    );
  }

  const t = data?.current.totals;
  const p = data?.previous;

  return (
    <div className="pt-2 pb-8 flex flex-col gap-5">
      {/* Header + the one filter row, above everything it controls. */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/admin" className="inline-flex items-center gap-1 text-xs font-extrabold text-muted hover:text-ink">
            <ArrowLeft size={13} /> Admin
          </Link>
          <h1 className="mt-1 flex items-center gap-2.5 text-2xl font-extrabold tracking-tight">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-primary-soft text-primary"><BarChart3 size={19} /></span>
            Analytics
          </h1>
          <p className="mt-1 text-sm text-muted font-semibold">
            {data ? `${fmtDay(data.range.start)} – ${fmtDay(data.range.end)} · ` : ""}learners only (admin accounts excluded) · IST
          </p>
        </div>
        <div className="flex gap-1 rounded-2xl bg-surface-2 p-1" role="radiogroup" aria-label="Date range">
          {RANGES.map((r) => (
            <button key={r} role="radio" aria-checked={range === r} onClick={() => { setError(null); setRange(r); }}
              className={`rounded-xl px-4 py-2 text-sm font-extrabold transition-colors ${range === r ? "bg-surface text-ink shadow-[var(--shadow-1)]" : "text-muted hover:text-ink"}`}>
              {r} days
            </button>
          ))}
        </div>
      </header>

      <ErrorNote message={error} />

      {!data || !t || !p || !derived ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, k) => <SkeletonCard key={k} lines={3} />)}
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <Kpi label="Active learners" value={t.active.toLocaleString()} range={range}
              d={delta(t.active, p.active)} spark={derived.spark("active")} />
            <Kpi label="Avg daily active" value={t.avg_daily_active.toFixed(1)} range={range}
              d={delta(t.avg_daily_active, p.avg_daily_active)} />
            <Kpi label="Screen time" value={fmtDuration(t.screen_seconds)} range={range}
              d={delta(t.screen_seconds, p.screen_seconds)} spark={derived.spark("screen_seconds")} />
            <Kpi label="Answers" value={t.answers.toLocaleString()} range={range}
              d={delta(t.answers, p.answers)} spark={derived.spark("answers")} />
            <Kpi label="Accuracy" value={t.accuracy === null ? "—" : fmtPct(t.accuracy)} range={range}
              d={delta(t.accuracy, p.accuracy, "ratio")} />
            <Kpi label="New learners" value={t.new_users.toLocaleString()} range={range}
              d={delta(t.new_users, p.new_users)} spark={derived.spark("new_users")} />
          </div>

          {/* Engagement */}
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard className="xl:col-span-2" title="Active learners"
              subtitle="Answered a question or used the app, per day"
              aside={<Legend items={[
                { label: "Daily", color: CONTEXT, kind: "bar" },
                { label: "7-day average", color: "var(--primary)", kind: "line" },
              ]} />}>
              <TimeChart label="Active learners per day" days={derived.days} height={260}
                bars={{ label: "active", values: derived.active }}
                line={{ label: "7-day avg", values: derived.activeAvg }} />
            </ChartCard>
            <ChartCard title="Engagement" subtitle={`Across the last ${range} days`}>
              {data.stickiness !== null
                ? <Meter value={data.stickiness} label="stickiness (daily ÷ monthly active)" />
                : <p className="text-sm text-muted font-semibold">Not enough activity yet.</p>}
              <div className="mt-4">
                <Fact label="Total learners" value={data.learners.toLocaleString()} />
                <Fact label="Quizzes finished" value={t.quizzes.toLocaleString()} />
                <Fact label="Screen time per active learner" value={fmtDuration(t.screen_per_active)} />
                <Fact label="Answers per active learner" value={t.active ? Math.round(t.answers / t.active).toLocaleString() : "0"} />
                <Fact label="Mock exams taken" value={data.exams.taken.toLocaleString()} />
              </div>
            </ChartCard>
          </div>

          {/* Time spent, output, accuracy — one measure per chart, never two scales on one plot. */}
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Screen time" subtitle="Foreground time, all learners combined">
              <TimeChart label="Screen time per day" days={derived.days} kind="duration"
                line={{ label: "screen time", values: derived.screen, area: true }} />
            </ChartCard>
            <ChartCard title="Answers" subtitle="Questions answered per day">
              <TimeChart label="Answers per day" days={derived.days} bars={{ label: "answers", values: derived.answers }} />
            </ChartCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Accuracy over time" subtitle="Share of answers that were correct, per day"
              aside={derived.overall === null ? undefined : <Legend items={[
                { label: "Daily", color: "var(--primary)", kind: "line" },
                { label: `Period average ${fmtPct(derived.overall)}`, color: "var(--ink-soft)", kind: "line" },
              ]} />}>
              {/* Taller: it shares a row with the subject list, which grows with the topic count. */}
              <TimeChart label="Accuracy per day" days={derived.days} kind="ratio" height={330}
                line={{ label: "correct", values: derived.accuracy }}
                reference={derived.overall === null ? undefined : { value: derived.overall, label: "period average" }} />
            </ChartCard>
            <ChartCard title="Accuracy by subject" subtitle="Hardest first · the line marks the overall average">
              <HBars label="Accuracy by subject" rows={derived.topicAcc} format={fmtPct} max={1}
                footnote={derived.topicAcc.some((r) => r.muted) ? SMALL_NOTE : undefined}
                reference={derived.overall === null ? undefined : { value: derived.overall, label: `overall ${fmtPct(derived.overall)}` }} />
            </ChartCard>
          </div>

          {/* What gets practised */}
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard title="Practice by subject" subtitle="Answers given">
              <HBars label="Answers by subject" format={(v) => v.toLocaleString()}
                rows={data.topics.map((tp) => ({ label: tp.name, icon: tp.icon, value: tp.answers, detail: `${tp.learners} learner${tp.learners === 1 ? "" : "s"}` }))} />
            </ChartCard>
            <ChartCard title="How learners practise" subtitle="Sessions started, by mode">
              <HBars label="Sessions by mode" format={(v) => v.toLocaleString()}
                rows={data.modes.map((m) => ({
                  label: MODE_LABEL[m.mode] ?? m.mode, value: m.started,
                  detail: `${m.started ? Math.round((m.finished / m.started) * 100) : 0}% finished`,
                }))} />
            </ChartCard>
            <div className="flex flex-col gap-4">
              <ChartCard title="Accuracy by difficulty">
                {/* Difficulty keeps its natural order (easy → hard) rather than a ranking. */}
                <HBars label="Accuracy by difficulty" format={fmtPct} max={1}
                  rows={data.difficulty.filter((d) => d.answers > 0).map((d) => ({
                    label: DIFFICULTY[d.difficulty - 1] ?? `Level ${d.difficulty}`, value: d.correct / d.answers,
                    detail: `${d.answers.toLocaleString()} answers`, muted: d.answers < MIN_SAMPLE }))}
                  footnote={data.difficulty.some((d) => d.answers > 0 && d.answers < MIN_SAMPLE) ? SMALL_NOTE : undefined} />
              </ChartCard>
              <ChartCard title="Accuracy by question source">
                <HBars label="Accuracy by source" format={fmtPct} max={1}
                  rows={rankAccuracy(data.sources, (src) => SOURCE_LABEL[src.source] ?? src.source)}
                  footnote={data.sources.some((src) => src.answers > 0 && src.answers < MIN_SAMPLE) ? SMALL_NOTE : undefined} />
              </ChartCard>
            </div>
          </div>

          {/* When */}
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard className="xl:col-span-2" title="When learners study" subtitle="Answers by weekday and hour (IST)">
              <HourHeatmap cells={data.heatmap} />
            </ChartCard>
            <ChartCard title="By weekday" subtitle="Answers, busiest day highlighted">
              <CategoryBars label="Answers by weekday" labels={WEEKDAYS.map((d) => d.label)} values={derived.weekday}
                highlight={derived.weekday.some((v) => v > 0) ? derived.busiestDay : undefined} height={230} />
            </ChartCard>
          </div>

          {/* Retention */}
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard className="xl:col-span-2" title="Retention by sign-up week"
              subtitle="Share of each week's new learners active in each week after joining">
              <Cohorts rows={data.cohorts} />
            </ChartCard>
            <ChartCard title="Current streaks" subtitle="Learners by streak length, in days">
              <CategoryBars label="Learners by streak length" labels={data.streaks.map((s) => s.label)}
                values={data.streaks.map((s) => s.users)} format={(v) => `${v} learner${v === 1 ? "" : "s"}`} height={230} />
            </ChartCard>
          </div>

          {/* Exams + people */}
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard title="Mock exam scores"
              subtitle={data.exams.taken ? `${data.exams.taken} taken · avg ${data.exams.avg_pct}% · best ${data.exams.best_pct}%` : "No exams finished in this range"}>
              <CategoryBars label="Exams by score band"
                labels={data.exams.distribution.map((b) => (b.label === "<0" ? "Below 0%" : `${b.label}%`))}
                ticks={data.exams.distribution.map((b) => b.label.split("–")[0])}
                values={data.exams.distribution.map((b) => b.count)} format={(v) => `${v} exam${v === 1 ? "" : "s"}`} height={230} />
              <p className="mt-2 text-[11px] font-semibold text-muted">Score band (%, lower bound) after −⅓ negative marking.</p>
            </ChartCard>
            <ChartCard className="xl:col-span-2" title="Most active learners" subtitle="By answers in this range">
              {data.top_learners.length === 0 ? (
                <p className="text-sm text-muted font-semibold py-6 text-center">No answers in this range yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] font-extrabold uppercase tracking-wider text-muted">
                      <th className="pb-2 pr-3">Learner</th><th className="pb-2 pr-3 text-right">Answers</th>
                      <th className="pb-2 pr-3 text-right">Accuracy</th><th className="pb-2 pr-3 text-right">Screen time</th>
                      <th className="pb-2 text-right">Streak</th>
                    </tr>
                  </thead>
                  <tbody className="tabular-nums">
                    {data.top_learners.map((l) => (
                      <tr key={l.name} className="border-t border-line font-semibold">
                        <td className="py-2 pr-3 font-extrabold">{l.name}</td>
                        <td className="py-2 pr-3 text-right">{l.answers.toLocaleString()}</td>
                        <td className="py-2 pr-3 text-right">{l.accuracy === null ? "—" : fmtPct(l.accuracy)}</td>
                        <td className="py-2 pr-3 text-right">{fmtDuration(l.screen_seconds)}</td>
                        <td className="py-2 text-right">{l.streak ? `${l.streak} days` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ChartCard>
          </div>

          <ChartCard title="Hardest questions" subtitle="Lowest accuracy among questions answered at least three times"
            aside={<Link href="/admin" className="inline-flex items-center gap-1 text-xs font-extrabold text-primary">Edit questions <ArrowRight size={13} /></Link>}>
            {data.hardest.length === 0 ? (
              <p className="text-sm text-muted font-semibold py-6 text-center">
                No question has three answers in this range yet — this fills in as learners practise.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[10px] font-extrabold uppercase tracking-wider text-muted">
                    <th className="pb-2 pr-3">Question</th><th className="pb-2 pr-3">Subject</th>
                    <th className="pb-2 pr-3 text-right">Answers</th><th className="pb-2 w-40">Accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hardest.map((q) => (
                    <tr key={q.id} className="border-t border-line font-semibold align-top">
                      <td className="py-2.5 pr-3 leading-snug">{q.text}</td>
                      <td className="py-2.5 pr-3 whitespace-nowrap text-ink-soft">{q.topic}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{q.attempts}</td>
                      <td className="py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="h-2 flex-1 rounded-full" style={{ background: "var(--danger-soft)" }}>
                            <div className="h-full rounded-full" style={{ width: `${q.accuracy * 100}%`, background: "var(--danger)" }} />
                          </div>
                          <span className="w-9 text-right text-[12px] font-extrabold tabular-nums">{fmtPct(q.accuracy)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </ChartCard>
        </>
      )}
    </div>
  );
}
