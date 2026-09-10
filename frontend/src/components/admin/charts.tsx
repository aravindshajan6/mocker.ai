"use client";

/**
 * A small SVG chart kit for the admin analytics page. Hand-rolled rather than a library to match
 * the rest of the app, and to hold the house mark specs exactly: columns capped at 24px with a
 * 4px rounded data end, 2px lines, hairline solid grid, text in text tokens (never series
 * colours), one primary hue plus a de-emphasis grey. Every chart is one tab stop: arrow keys
 * scrub the data and a live region reads it out, so keyboard users get what hover gives.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ format ---- */

export function fmtDuration(seconds: number): string {
  if (seconds < 60) return seconds > 0 ? "<1m" : "0m";
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h >= 100) return `${Math.round(m / 60).toLocaleString()}h`;   // minutes are noise at this scale
  return rest ? `${h}h ${rest}m` : `${h}h`;
}
export const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
export const fmtPct = (x: number) => `${Math.round(x * 100)}%`;

const PRIMARY = "var(--primary)";
/** Context marks behind the primary: clearly there (2.3:1 light, 3.2:1 dark), never competing. */
export const CONTEXT = "color-mix(in oklab, var(--muted) 60%, var(--surface))";

/* ------------------------------------------------------------------- scale ---- */

const COUNT_STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000];
const DURATION_STEPS = [60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 172800];
const RATIO_STEPS = [0.1, 0.2, 0.25, 0.5];

/** Clean axis ticks (0 / 5 / 10 …) from a list of human-friendly steps for the unit. */
export function niceTicks(max: number, kind: "count" | "duration" | "ratio" = "count", target = 4): number[] {
  if (kind === "ratio") {
    const step = RATIO_STEPS.find((s) => 1 / s <= target + 1) ?? 0.25;
    return Array.from({ length: Math.round(1 / step) + 1 }, (_, i) => +(i * step).toFixed(4));
  }
  const steps = kind === "duration" ? DURATION_STEPS : COUNT_STEPS;
  const m = Math.max(max, kind === "duration" ? 60 : 1);
  const step = steps.find((s) => m / s <= target) ?? steps[steps.length - 1];
  const top = Math.ceil(m / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
}

/* ------------------------------------------------------------------- hooks ---- */

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/** One tab stop per chart; arrows move through the data, Escape lets go. */
function useScrub(n: number) {
  const [i, setI] = useState<number | null>(null);
  const bind = {
    tabIndex: 0,
    onKeyDown: (e: React.KeyboardEvent) => {
      const k = e.key;
      if (k === "ArrowRight" || k === "ArrowDown") { e.preventDefault(); setI((v) => Math.min(n - 1, (v ?? -1) + 1)); }
      else if (k === "ArrowLeft" || k === "ArrowUp") { e.preventDefault(); setI((v) => Math.max(0, (v ?? n) - 1)); }
      else if (k === "Home") { e.preventDefault(); setI(0); }
      else if (k === "End") { e.preventDefault(); setI(n - 1); }
      else if (k === "Escape") setI(null);
    },
    onBlur: () => setI(null),
    onPointerLeave: () => setI(null),
  };
  return { i, setI, bind };
}

/* --------------------------------------------------------------- chrome ---- */

export function ChartCard({ title, subtitle, aside, children, className = "" }: {
  title: string; subtitle?: string; aside?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card p-5 ${className}`}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 className="font-extrabold text-[15px] leading-tight">{title}</h2>
          {subtitle && <p className="text-xs text-muted font-semibold mt-0.5">{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

function tipTransform(xFrac: number, below = false) {
  const x = xFrac < 0.15 ? "-8%" : xFrac > 0.85 ? "-92%" : "-50%";
  return `translate(${x}, ${below ? "0" : "-100%"})`;
}

type TipRow = { value: string; label: string; swatch?: "line" | "bar"; color?: string };

/** Values lead, labels follow; series keyed with a short line or bar in the series colour. */
function Tooltip({ left, top, xFrac, heading, rows, below = false }: {
  left: number; top: number; xFrac: number; heading: string; rows: TipRow[]; below?: boolean;
}) {
  return (
    <div role="presentation" style={{ left, top, transform: tipTransform(xFrac, below) }}
      className="pointer-events-none absolute z-20 min-w-24 rounded-xl border border-line bg-surface px-3 py-2 shadow-[var(--shadow-3)]">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted whitespace-nowrap">{heading}</p>
      {rows.map((r) => (
        <div key={r.label} className="mt-1 flex items-center gap-2 whitespace-nowrap">
          {r.swatch && (
            <span className="shrink-0" style={{
              width: r.swatch === "line" ? 12 : 8, height: r.swatch === "line" ? 2 : 8,
              borderRadius: 2, background: r.color,
            }} />
          )}
          <span className="text-sm font-extrabold">{r.value}</span>
          <span className="text-[11px] font-semibold text-muted">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; kind: "line" | "bar" }[] }) {
  return (
    <div className="flex items-center gap-4 text-[11px] font-bold text-ink-soft">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span style={{
            width: it.kind === "line" ? 14 : 10, height: it.kind === "line" ? 2 : 10,
            borderRadius: 2, background: it.color, display: "inline-block",
          }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

/** A column with only its data end rounded (4px) and a square foot on the baseline. */
function columnPath(x: number, y: number, w: number, h: number) {
  if (h <= 0) return "";
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

const M = { top: 14, right: 12, bottom: 24, left: 44 };

function Axes({ w, h, ticks, y, fmt, xLabels }: {
  w: number; h: number; ticks: number[]; y: (v: number) => number; fmt: (v: number) => string;
  xLabels: { x: number; text: string; anchor?: "start" | "middle" | "end" }[];
}) {
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={M.left} x2={w - M.right} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
          <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={10} fontWeight={700}
            fill="var(--muted)" style={{ fontVariantNumeric: "tabular-nums" }}>{fmt(t)}</text>
        </g>
      ))}
      {xLabels.map((l) => (
        <text key={`${l.x}-${l.text}`} x={l.x} y={h - 6} textAnchor={l.anchor ?? "middle"} fontSize={10}
          fontWeight={700} fill="var(--muted)">{l.text}</text>
      ))}
    </g>
  );
}

function dateLabels(days: string[], x: (i: number) => number) {
  if (!days.length) return [];
  const last = days.length - 1;
  const idx = [...new Set([0, Math.round(last / 3), Math.round((2 * last) / 3), last])];
  return idx.map((i) => ({
    x: x(i), text: i === last ? "Today" : fmtDay(days[i]),
    anchor: (i === 0 ? "start" : i === last ? "end" : "middle") as "start" | "middle" | "end",
  }));
}

/* ------------------------------------------------------------ time series ---- */

/**
 * Days on the x axis. `bars` draws columns, `line` a 2px line (with a 10% area wash when it is
 * the only series). Nulls in a line are gaps, not zeros — a day with no answers has no accuracy.
 */
export function TimeChart({ days, bars, line, kind = "count", height = 220, reference, label }: {
  days: string[];
  bars?: { label: string; values: number[]; color?: string };
  line?: { label: string; values: (number | null)[]; color?: string; area?: boolean };
  kind?: "count" | "duration" | "ratio";
  height?: number;
  reference?: { value: number; label: string };
  label: string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const n = days.length;
  const { i, setI, bind } = useScrub(n);
  const fmt = kind === "duration" ? fmtDuration : kind === "ratio" ? fmtPct
    : (v: number) => (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(1));
  const all = [...(bars?.values ?? []), ...((line?.values ?? []).filter((v) => v !== null) as number[]),
    reference?.value ?? 0];
  const ticks = niceTicks(Math.max(0, ...all), kind);
  const top = ticks[ticks.length - 1] || 1;
  const innerW = Math.max(0, w - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const band = n ? innerW / n : 0;
  const x = (k: number) => M.left + band * (k + 0.5);
  const y = (v: number) => M.top + innerH - (v / top) * innerH;
  const barW = Math.max(1, Math.min(24, band - 2));      // 2px surface gap between neighbours

  const lineColor = line?.color ?? PRIMARY;
  const barColor = bars?.color ?? (line ? CONTEXT : PRIMARY);
  let path = "";
  let area = "";
  if (line && w) {
    let open = false;
    let segStart = 0;
    line.values.forEach((v, k) => {
      if (v === null) {
        if (open && line.area) area += `L${x(k - 1)},${y(0)}L${x(segStart)},${y(0)}Z`;
        open = false;
        return;
      }
      path += `${open ? "L" : "M"}${x(k)},${y(v)}`;
      if (line.area) area += `${open ? "L" : "M"}${x(k)},${y(v)}`;
      if (!open) segStart = k;
      open = true;
    });
    if (open && line.area) area += `L${x(n - 1)},${y(0)}L${x(segStart)},${y(0)}Z`;
  }
  const lastIdx = line ? line.values.map((v, k) => (v === null ? -1 : k)).filter((k) => k >= 0).pop() : undefined;

  const readout = i === null ? "" : [
    fmtDay(days[i]),
    bars && `${bars.label} ${fmt(bars.values[i])}`,
    line && line.values[i] !== null && `${line.label} ${fmt(line.values[i] as number)}`,
  ].filter(Boolean).join(", ");

  return (
    <div ref={ref} {...bind} role="group" aria-label={`${label}. Arrow keys read each day.`}
      className="relative rounded-lg outline-offset-4"
      onPointerMove={(e) => {
        if (!band) return;
        const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const k = Math.floor((e.clientX - r.left - M.left) / band);
        setI(k >= 0 && k < n ? k : null);
      }}>
      {w > 0 && (
        <svg width={w} height={height} className="block overflow-visible">
          <Axes w={w} h={height} ticks={ticks} y={y} fmt={kind === "count" ? (v) => v.toLocaleString() : fmt}
            xLabels={dateLabels(days, x)} />
          {bars?.values.map((v, k) => (
            <path key={k} d={columnPath(x(k) - barW / 2, y(v), barW, y(0) - y(v))} fill={barColor}
              opacity={i === null || i === k || line ? 1 : 0.45} />
          ))}
          {/* Named in the card's legend, not in the plot — an in-plot label collides with the data. */}
          {reference && (
            <line x1={M.left} x2={w - M.right} y1={y(reference.value)} y2={y(reference.value)}
              stroke="var(--ink-soft)" strokeWidth={1} opacity={0.55} />
          )}
          {line && area && <path d={area} fill={lineColor} opacity={0.1} />}
          {line && path && <path d={path} fill="none" stroke={lineColor} strokeWidth={2}
            strokeLinejoin="round" strokeLinecap="round" />}
          {line && lastIdx !== undefined && lastIdx >= 0 && i === null && (
            <circle cx={x(lastIdx)} cy={y(line.values[lastIdx] as number)} r={4} fill={lineColor}
              stroke="var(--surface)" strokeWidth={2} />
          )}
          {i !== null && (
            <g>
              <line x1={x(i)} x2={x(i)} y1={M.top} y2={M.top + innerH} stroke="var(--ink-soft)" strokeWidth={1} opacity={0.35} />
              {line && line.values[i] !== null && (
                <circle cx={x(i)} cy={y(line.values[i] as number)} r={4.5} fill={lineColor}
                  stroke="var(--surface)" strokeWidth={2} />
              )}
            </g>
          )}
        </svg>
      )}
      {i !== null && w > 0 && (
        <Tooltip left={x(i)} top={M.top + 4} xFrac={x(i) / w} heading={fmtDay(days[i])} rows={[
          ...(line && line.values[i] !== null
            ? [{ value: fmt(line.values[i] as number), label: line.label, swatch: "line" as const, color: lineColor }] : []),
          ...(bars ? [{ value: fmt(bars.values[i]), label: bars.label, swatch: "bar" as const, color: barColor }] : []),
        ]} />
      )}
      <span className="sr-only" aria-live="polite">{readout}</span>
    </div>
  );
}

/* -------------------------------------------------------- categorical bars ---- */

/** Columns over named categories (weekdays, score bands, streak lengths). */
export function CategoryBars({ labels, ticks: tickLabels, values, format = (v: number) => v.toLocaleString(), height = 200, label, highlight }: {
  labels: string[]; values: number[]; format?: (v: number) => string; height?: number; label: string;
  highlight?: number;
  /** Short axis labels when the full names (kept for the tooltip) would collide. */
  ticks?: string[];
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const n = labels.length;
  const { i, setI, bind } = useScrub(n);
  const ticks = niceTicks(Math.max(0, ...values));
  const top = ticks[ticks.length - 1] || 1;
  const innerW = Math.max(0, w - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const band = n ? innerW / n : 0;
  const x = (k: number) => M.left + band * (k + 0.5);
  const y = (v: number) => M.top + innerH - (v / top) * innerH;
  const barW = Math.max(1, Math.min(24, band - 2));
  return (
    <div ref={ref} {...bind} role="group" aria-label={`${label}. Arrow keys read each bar.`}
      className="relative rounded-lg outline-offset-4">
      {w > 0 && (
        <svg width={w} height={height} className="block overflow-visible">
          <Axes w={w} h={height} ticks={ticks} y={y} fmt={(v) => v.toLocaleString()}
            xLabels={(tickLabels ?? labels).map((l, k) => ({ x: x(k), text: l }))} />
          {values.map((v, k) => (
            <g key={k} onPointerEnter={() => setI(k)}>
              <rect x={x(k) - band / 2} y={M.top} width={band} height={innerH} fill="transparent" />
              <path d={columnPath(x(k) - barW / 2, y(v), barW, y(0) - y(v))}
                fill={highlight === undefined || highlight === k ? PRIMARY : CONTEXT}
                opacity={i === null || i === k ? 1 : 0.45} />
            </g>
          ))}
        </svg>
      )}
      {i !== null && w > 0 && (
        <Tooltip left={x(i)} top={Math.max(M.top, y(values[i]) - 6)} xFrac={x(i) / w} heading={labels[i]}
          rows={[{ value: format(values[i]), label }]} />
      )}
      <span className="sr-only" aria-live="polite">{i === null ? "" : `${labels[i]}: ${format(values[i])}`}</span>
    </div>
  );
}

/**
 * Horizontal bars: the form for ranked categories with long names. The value rides the bar tip;
 * a reference line (e.g. the overall average) is a solid hairline, never dashed.
 */
export function HBars({ rows, format, max, reference, label, empty = "No data in this range yet.", footnote }: {
  rows: { label: string; value: number; detail?: string; icon?: string; muted?: boolean }[];
  format: (v: number) => string;
  max?: number;
  reference?: { value: number; label: string };
  label: string;
  empty?: string;
  footnote?: string;
}) {
  const { i, setI, bind } = useScrub(rows.length);
  if (!rows.length) return <p className="text-sm text-muted font-semibold py-6 text-center">{empty}</p>;
  const top = max ?? Math.max(...rows.map((r) => r.value), reference?.value ?? 0, 1);
  return (
    <div {...bind} role="group" aria-label={`${label}. Arrow keys read each row.`}
      className="relative flex flex-col gap-2 rounded-lg outline-offset-4">
      {rows.map((r, k) => {
        const pct = Math.max(0, Math.min(1, r.value / top)) * 100;
        const dim = i !== null && i !== k;
        return (
          <div key={r.label} className="flex items-center gap-3" onPointerEnter={() => setI(k)}>
            <span className="w-40 shrink-0 truncate text-[12px] font-bold text-ink-soft" title={r.label}>
              {r.icon && <span className="mr-1">{r.icon}</span>}{r.label}
            </span>
            <div className="relative flex-1 h-5">
              {reference && (
                <span className="absolute top-[-3px] bottom-[-3px] w-px"
                  style={{ left: `${(reference.value / top) * 100}%`, background: "var(--ink-soft)", opacity: 0.45 }} />
              )}
              <div className="absolute left-0 top-[3px] h-[14px] transition-opacity duration-150"
                style={{ width: `${pct}%`, background: r.muted ? CONTEXT : PRIMARY, borderRadius: "0 4px 4px 0", opacity: dim ? 0.45 : 1 }} />
              <span className={`absolute top-1/2 -translate-y-1/2 pl-1.5 text-[11px] font-extrabold whitespace-nowrap ${r.muted ? "text-muted" : ""}`}
                style={{ left: `${pct}%` }}>{format(r.value)}</span>
            </div>
            {r.detail && <span className="w-24 shrink-0 text-right text-[11px] font-semibold text-muted tabular-nums">{r.detail}</span>}
          </div>
        );
      })}
      {(reference || footnote) && (
        <p className="mt-1 flex flex-wrap gap-x-4 text-[10px] font-extrabold text-muted">
          {reference && (
            <span><span className="inline-block w-3 h-px align-middle mr-1.5" style={{ background: "var(--ink-soft)" }} />{reference.label}</span>
          )}
          {footnote && <span>{footnote}</span>}
        </p>
      )}
      <span className="sr-only" aria-live="polite">
        {i === null ? "" : `${rows[i].label}: ${format(rows[i].value)}${rows[i].detail ? `, ${rows[i].detail}` : ""}`}
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------- heatmap ---- */

const HEAT = ["var(--surface-2)", "var(--heat-1)", "var(--heat-2)", "var(--heat-3)", "var(--heat-4)"];

/** Four validated steps plus an explicit empty class. */
export function heatStep(q: number): number {
  if (q <= 0) return 0;
  return q > 0.75 ? 4 : q > 0.5 ? 3 : q > 0.25 ? 2 : 1;
}

export function HeatLegend({ note }: { note?: string }) {
  return (
    <div className="mt-3 flex items-center gap-1.5 text-[10px] font-bold text-muted" aria-hidden>
      <span>Less</span>
      {HEAT.map((c) => <span key={c} className="h-3 w-3 rounded-[3px]" style={{ background: c }} />)}
      <span>More</span>
      {note && <span className="ml-auto">{note}</span>}
    </div>
  );
}

const WEEK = [
  { dow: 1, label: "Mon" }, { dow: 2, label: "Tue" }, { dow: 3, label: "Wed" }, { dow: 4, label: "Thu" },
  { dow: 5, label: "Fri" }, { dow: 6, label: "Sat" }, { dow: 0, label: "Sun" },
];
export const WEEKDAYS = WEEK;

/* Grid geometry, shared by the cells and the tooltip that must land on them. */
const HM = { pad: 4, label: 36, gap: 3, row: 24 };

export function HourHeatmap({ cells }: { cells: { dow: number; hour: number; answers: number }[] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const map = new Map(cells.map((c) => [`${c.dow}:${c.hour}`, c.answers]));
  const busiest = Math.max(0, ...cells.map((c) => c.answers));
  const max = Math.max(1, busiest);             // floor of 1 only guards the division
  const at = (row: number, hour: number) => map.get(`${WEEK[row].dow}:${hour}`) ?? 0;
  const [active, setActive] = useState<{ row: number; hour: number } | null>(null);
  const onKeyDown = (e: React.KeyboardEvent) => {
    const c = active ?? { row: 0, hour: -1 };
    const next: Record<string, { row: number; hour: number }> = {
      ArrowRight: { row: c.row, hour: Math.min(23, c.hour + 1) },
      ArrowLeft: { row: c.row, hour: Math.max(0, c.hour - 1) },
      ArrowDown: { row: Math.min(6, c.row + 1), hour: Math.max(0, c.hour) },
      ArrowUp: { row: Math.max(0, c.row - 1), hour: Math.max(0, c.hour) },
    };
    if (next[e.key]) { e.preventDefault(); setActive(next[e.key]); }
    if (e.key === "Escape") setActive(null);
  };
  const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;
  const cellW = (w - 2 * HM.pad - HM.label - HM.gap - HM.gap * 23) / 24;
  const cellX = (hour: number) => HM.pad + HM.label + HM.gap + hour * (cellW + HM.gap) + cellW / 2;
  // Top two rows open their tooltip downward, so it never covers the card's heading.
  const cellY = (row: number) => row < 2
    ? HM.pad + (row + 1) * (HM.row + HM.gap) + 2
    : HM.pad + row * (HM.row + HM.gap) - 4;
  return (
    <div>
      <div ref={ref} tabIndex={0} role="group" aria-label="Study hours grid. Arrow keys read each hour."
        onKeyDown={onKeyDown} onBlur={() => setActive(null)} onPointerLeave={() => setActive(null)}
        className="relative rounded-lg p-1 outline-offset-2">
        {WEEK.map((d, row) => (
          <div key={d.dow} className="flex items-center gap-[3px] mb-[3px]">
            <span className="w-9 shrink-0 text-[11px] font-bold text-muted">{d.label}</span>
            {Array.from({ length: 24 }, (_, hour) => {
              const v = at(row, hour);
              const lit = active?.row === row && active.hour === hour;
              return (
                <div key={hour} onPointerEnter={() => setActive({ row, hour })}
                  className="flex-1 h-6 rounded-[4px]"
                  style={{
                    background: HEAT[heatStep(v / max)],
                    outline: lit ? "2px solid var(--ink)" : undefined, outlineOffset: 1,
                  }} />
              );
            })}
          </div>
        ))}
        <div className="flex items-center gap-[3px] mt-1">
          <span className="w-9 shrink-0" />
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="flex-1 text-center text-[10px] font-bold text-muted tabular-nums">
              {h % 3 === 0 ? String(h).padStart(2, "0") : ""}
            </span>
          ))}
        </div>
        {active && w > 0 && (
          <Tooltip xFrac={(active.hour + 0.5) / 24} below={active.row < 2}
            left={cellX(active.hour)} top={cellY(active.row)} heading={`${WEEK[active.row].label} · ${hh(active.hour)}`}
            rows={[{ value: at(active.row, active.hour).toLocaleString(), label: "answers" }]} />
        )}
        <span className="sr-only" aria-live="polite">
          {active ? `${WEEK[active.row].label} ${hh(active.hour)}: ${at(active.row, active.hour)} answers` : ""}
        </span>
      </div>
      <HeatLegend note={busiest
        ? `busiest hour: ${busiest.toLocaleString()} answer${busiest === 1 ? "" : "s"}`
        : "no answers in this range"} />
    </div>
  );
}

/* ---------------------------------------------------------------- sparkline ---- */

/** Twelve-ish points in the de-emphasis hue, with the current value marked in the primary. */
export function Sparkline({ values, width = 84, height = 26 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const x = (k: number) => 2 + (k / (values.length - 1)) * (width - 4);
  const y = (v: number) => height - 3 - (v / max) * (height - 6);
  const d = values.map((v, k) => `${k ? "L" : "M"}${x(k)},${y(v)}`).join("");
  const last = values.length - 1;
  return (
    <svg width={width} height={height} aria-hidden className="shrink-0">
      <path d={d} fill="none" stroke={CONTEXT} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last])} r={3} fill={PRIMARY} stroke="var(--surface)" strokeWidth={1.5} />
    </svg>
  );
}
