"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, BookOpenCheck, CalendarRange, Clock, UserPlus, Users } from "lucide-react";
import { ErrorNote, Item, SkeletonCard } from "@/components/ui";
import { api } from "@/lib/api";
import type { AdminAnalytics as Data } from "@/lib/types";

/* ------------------------------------------------------------------ format ---- */

export function fmtDuration(seconds: number): string {
  if (seconds < 60) return seconds > 0 ? "<1m" : "0m";
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h}h ${rest}m` : `${h}h`;
}

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

// Postgres DOW is 0 = Sunday; the grid reads Monday-first, the way a study week is planned.
const DAYS = [
  { dow: 1, label: "Mon" }, { dow: 2, label: "Tue" }, { dow: 3, label: "Wed" }, { dow: 4, label: "Thu" },
  { dow: 5, label: "Fri" }, { dow: 6, label: "Sat" }, { dow: 0, label: "Sun" },
];
const hourLabel = (h: number) => `${String(h).padStart(2, "0")}:00`;

/**
 * Where a tooltip sits relative to its anchor. Near either edge it shifts inward instead of
 * centring, so it never hangs off the card; `below` flips it under the anchor, for marks at the
 * top of a scrolling container that would otherwise clip it.
 */
function tipTransform(xFrac: number, below = false): string {
  const x = xFrac < 0.18 ? "-12%" : xFrac > 0.82 ? "-88%" : "-50%";
  return `translate(${x}, ${below ? "0" : "-100%"})`;
}

/* ------------------------------------------------------------------- tiles ---- */

function Tile({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="card p-3.5">
      <div className="text-muted mb-1">{icon}</div>
      {/* Proportional figures: tabular digits look loose on a standalone value. */}
      <div className="text-xl font-extrabold leading-none">{value}</div>
      <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mt-1.5">{label}</div>
      {sub && <div className="text-[11px] font-semibold text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

/* ------------------------------------------------------------ column chart ---- */

/**
 * One series over days. Columns cap at 24px with a 4px rounded top and a square baseline; the
 * slot, not the painted bar, is the hover target. One tab stop — arrow keys scrub the days and a
 * live region reads the value out, so keyboard users get what pointer users get.
 */
function ColumnChart({ title, rows, value, format, describe }: {
  title: string;
  rows: Data["series"];
  value: (r: Data["series"][number]) => number;
  format: (n: number) => string;
  describe: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const values = rows.map(value);
  const max = Math.max(1, ...values);
  const peak = values.indexOf(Math.max(...values));
  const last = rows.length - 1;
  const readout = active === null ? "" : `${fmtDay(rows[active].day)}: ${format(values[active])}`;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); setActive((i) => Math.min(last, (i ?? -1) + 1)); }
    if (e.key === "ArrowLeft") { e.preventDefault(); setActive((i) => Math.max(0, (i ?? rows.length) - 1)); }
    if (e.key === "Escape") setActive(null);
  };

  return (
    <div className="card p-4">
      <p className="font-extrabold text-sm">{title}</p>
      <p className="text-[11px] text-muted font-semibold">{describe}</p>
      <div
        tabIndex={0} role="group" aria-label={`${title}. Use the arrow keys to read each day.`}
        onKeyDown={onKey} onBlur={() => setActive(null)} onPointerLeave={() => setActive(null)}
        className="relative mt-4 rounded-lg outline-offset-4"
      >
        {/* peak value, labelled once rather than a number on every column */}
        <div className="flex items-end h-36 border-b border-line" style={{ gap: 2 }}>
          {rows.map((r, i) => {
            const v = values[i];
            const h = v ? Math.max(4, (v / max) * 100) : 0;
            const lit = active === i;
            return (
              <div key={r.day} className="relative flex-1 h-full flex items-end justify-center"
                onPointerEnter={() => setActive(i)}>
                {i === peak && v > 0 && active === null && (
                  <span className="absolute text-[10px] font-extrabold text-ink-soft whitespace-nowrap"
                    style={{ bottom: `calc(${h}% + 4px)` }}>{format(v)}</span>
                )}
                <div className="w-full transition-[filter,opacity] duration-150"
                  style={{
                    maxWidth: 24, height: `${h}%`,
                    background: "var(--primary)", borderRadius: "4px 4px 0 0",
                    opacity: active === null || lit ? 1 : 0.45,
                  }} />
              </div>
            );
          })}
        </div>
        <div className="mt-1.5 flex justify-between text-[10px] font-bold text-muted tabular-nums">
          <span>{fmtDay(rows[0].day)}</span>
          <span>{fmtDay(rows[Math.floor(last / 2)].day)}</span>
          <span>Today</span>
        </div>

        {active !== null && (
          <div role="presentation"
            className="pointer-events-none absolute -top-2 z-10 rounded-xl border border-line bg-surface px-2.5 py-1.5 shadow-[var(--shadow-2)]"
            style={{ left: `${((active + 0.5) / rows.length) * 100}%`, transform: tipTransform((active + 0.5) / rows.length) }}>
            <p className="text-sm font-extrabold leading-tight whitespace-nowrap">{format(values[active])}</p>
            <p className="text-[10px] font-bold text-muted whitespace-nowrap">{fmtDay(rows[active].day)}</p>
          </div>
        )}
        <span className="sr-only" aria-live="polite">{readout}</span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- heatmap ---- */

/** Four validated steps plus an explicit empty cell — five visual classes in all. */
function heatStep(n: number, max: number): string {
  if (!n) return "var(--surface-2)";
  const q = n / max;
  return q > 0.75 ? "var(--heat-4)" : q > 0.5 ? "var(--heat-3)" : q > 0.25 ? "var(--heat-2)" : "var(--heat-1)";
}

function StudyHours({ cells }: { cells: Data["heatmap"] }) {
  const grid = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of cells) m.set(`${c.dow}:${c.hour}`, c.answers);
    return m;
  }, [cells]);
  const max = Math.max(1, ...cells.map((c) => c.answers));
  const [active, setActive] = useState<{ row: number; hour: number } | null>(null);
  const at = (row: number, hour: number) => grid.get(`${DAYS[row].dow}:${hour}`) ?? 0;
  const readout = active
    ? `${DAYS[active.row].label} ${hourLabel(active.hour)}: ${at(active.row, active.hour)} answers`
    : "";

  const onKey = (e: React.KeyboardEvent) => {
    const cur = active ?? { row: 0, hour: -1 };
    const moves: Record<string, { row: number; hour: number }> = {
      ArrowRight: { row: cur.row, hour: Math.min(23, cur.hour + 1) },
      ArrowLeft: { row: cur.row, hour: Math.max(0, cur.hour - 1) },
      ArrowDown: { row: Math.min(6, cur.row + 1), hour: Math.max(0, cur.hour) },
      ArrowUp: { row: Math.max(0, cur.row - 1), hour: Math.max(0, cur.hour) },
    };
    if (moves[e.key]) { e.preventDefault(); setActive(moves[e.key]); }
    if (e.key === "Escape") setActive(null);
  };

  return (
    <div className="card p-4">
      <p className="font-extrabold text-sm">When learners study</p>
      <p className="text-[11px] text-muted font-semibold">Answers by weekday and hour (IST), last 30 days</p>

      {/* p-1: room for the hovered cell's scale + outline, which the scroll box would clip. */}
      <div className="mt-2 overflow-x-auto p-1">
        <div
          tabIndex={0} role="group" aria-label="Study hours grid. Use the arrow keys to read each hour."
          onKeyDown={onKey} onBlur={() => setActive(null)} onPointerLeave={() => setActive(null)}
          className="relative min-w-[520px] rounded-lg outline-offset-4"
        >
          {DAYS.map((d, row) => (
            <div key={d.dow} className="flex items-center gap-[2px] mb-[2px]">
              <span className="w-9 shrink-0 text-[10px] font-bold text-muted">{d.label}</span>
              {Array.from({ length: 24 }, (_, hour) => {
                const n = at(row, hour);
                const lit = active?.row === row && active.hour === hour;
                return (
                  <div key={hour} onPointerEnter={() => setActive({ row, hour })}
                    className="flex-1 aspect-square rounded-[3px] transition-transform duration-100"
                    style={{
                      background: heatStep(n, max),
                      outline: lit ? "2px solid var(--ink)" : undefined, outlineOffset: 1,
                      transform: lit ? "scale(1.15)" : undefined, position: "relative", zIndex: lit ? 1 : 0,
                    }} />
                );
              })}
            </div>
          ))}
          <div className="flex items-center gap-[2px] mt-1">
            <span className="w-9 shrink-0" />
            {Array.from({ length: 24 }, (_, h) => (
              <span key={h} className="flex-1 text-center text-[9px] font-bold text-muted tabular-nums">
                {h % 3 === 0 ? String(h).padStart(2, "0") : ""}
              </span>
            ))}
          </div>

          {active && (
            <div role="presentation"
              className="pointer-events-none absolute z-10 rounded-xl border border-line bg-surface px-2.5 py-1.5 shadow-[var(--shadow-2)]"
              style={{
                left: `calc(36px + (100% - 36px) * ${(active.hour + 0.5) / 24})`,
                // The grid scrolls horizontally, which clips anything above it — so the top two
                // rows show their tooltip underneath the cell instead.
                top: active.row < 2
                  ? `calc(${active.row + 1} * (100% - 14px) / 7 + 4px)`
                  : `calc(${active.row} * (100% - 14px) / 7 - 4px)`,
                transform: tipTransform((active.hour + 0.5) / 24, active.row < 2),
              }}>
              <p className="text-sm font-extrabold leading-tight whitespace-nowrap">{at(active.row, active.hour)} answers</p>
              <p className="text-[10px] font-bold text-muted whitespace-nowrap">
                {DAYS[active.row].label} · {hourLabel(active.hour)}
              </p>
            </div>
          )}
          <span className="sr-only" aria-live="polite">{readout}</span>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-[10px] font-bold text-muted" aria-hidden>
        <span>Less</span>
        {["var(--surface-2)", "var(--heat-1)", "var(--heat-2)", "var(--heat-3)", "var(--heat-4)"].map((c) => (
          <span key={c} className="h-3 w-3 rounded-[3px]" style={{ background: c }} />
        ))}
        <span>More</span>
        <span className="ml-auto">busiest slot: {max} answers</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------- page ---- */

export default function AdminAnalytics() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.adminAnalytics(30)
      .then((d) => { if (alive) setData(d); })
      .catch((e: Error) => { if (alive) setError(e?.message || "Could not load usage analytics."); });
    return () => { alive = false; };
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Item><SkeletonCard lines={4} /></Item>;
  const s = data.summary;

  return (
    <>
      <Item>
        <div className="flex items-baseline justify-between gap-2">
          <p className="font-extrabold">Usage</p>
          <p className="text-[11px] text-muted font-semibold">Last {data.days} days · IST · admin accounts excluded</p>
        </div>
        <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Tile icon={<Activity size={14} />} label="Active today" value={s.active_today.toLocaleString()}
            sub={`of ${s.learners.toLocaleString()} learners`} />
          <Tile icon={<CalendarRange size={14} />} label="Active this week" value={s.active_week.toLocaleString()}
            sub={`${s.active_month.toLocaleString()} this month`} />
          <Tile icon={<Clock size={14} />} label="Screen time this week" value={fmtDuration(s.screen_seconds_week)}
            sub={s.active_week ? `${fmtDuration(s.avg_screen_seconds_week)} per active learner` : "no activity yet"} />
          <Tile icon={<BookOpenCheck size={14} />} label="Answers this week" value={s.answers_week.toLocaleString()}
            sub={`${s.quizzes_week.toLocaleString()} quizzes finished`} />
          <Tile icon={<UserPlus size={14} />} label="New learners" value={s.new_month.toLocaleString()} sub="last 30 days" />
          <Tile icon={<Users size={14} />} label="Screen time, all time" value={fmtDuration(s.screen_seconds_total)}
            sub="since tracking began" />
        </div>
      </Item>

      <Item>
        <div className="grid gap-3 lg:grid-cols-2">
          <ColumnChart title="Active learners per day" rows={data.series} value={(r) => r.active_users}
            format={(n) => `${n} active`} describe="Anyone who answered a question or used the app that day" />
          {/* A separate chart, not a second axis: learners and minutes share no scale. */}
          <ColumnChart title="Screen time per day" rows={data.series} value={(r) => r.screen_seconds}
            format={fmtDuration} describe="Foreground time, all learners combined" />
        </div>
      </Item>

      <Item><StudyHours cells={data.heatmap} /></Item>

      <Item>
        <details className="card p-4 group">
          <summary className="cursor-pointer text-sm font-extrabold">View the daily numbers as a table</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-extrabold uppercase tracking-wider text-muted">
                  <th className="py-1.5 pr-3">Day</th><th className="py-1.5 pr-3 text-right">Active</th>
                  <th className="py-1.5 pr-3 text-right">Screen time</th><th className="py-1.5 pr-3 text-right">Answers</th>
                  <th className="py-1.5 text-right">New</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {[...data.series].reverse().map((r) => (
                  <tr key={r.day} className="border-t border-line font-semibold">
                    <td className="py-1.5 pr-3">{fmtDay(r.day)}</td>
                    <td className="py-1.5 pr-3 text-right">{r.active_users}</td>
                    <td className="py-1.5 pr-3 text-right">{fmtDuration(r.screen_seconds)}</td>
                    <td className="py-1.5 pr-3 text-right">{r.answers}</td>
                    <td className="py-1.5 text-right">{r.new_users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Item>
    </>
  );
}
