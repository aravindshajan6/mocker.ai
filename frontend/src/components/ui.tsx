"use client";

import NumberFlow from "@number-flow/react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ bars ---- */
export function ProgressBar({ value, className = "", color = "var(--primary)" }:
  { value: number; className?: string; color?: string }) {
  const pct = Math.min(100, Math.max(0, value * 100));
  return (
    <div className={`h-2.5 w-full rounded-full bg-surface-2 overflow-hidden ${className}`}
      role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      {/* scaleX, not width: width animates layout+paint on every answered question, while a
          transform stays on the compositor. At 2.5px tall the corner distortion is invisible. */}
      <motion.div className="h-full w-full rounded-full origin-left" style={{ background: color }}
        initial={{ scaleX: 0 }} animate={{ scaleX: pct / 100 }}
        transition={{ type: "spring", visualDuration: 0.5, bounce: 0.15 }} />
    </div>
  );
}

/** A circular progress dial — used where a number deserves more weight than a bar gives it. */
export function ProgressRing({ value, size = 76, stroke = 7, color = "var(--primary)", children }:
  { value: number; size?: number; stroke?: number; color?: string; children?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, Math.max(0, value));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={{ type: "spring", visualDuration: 0.8, bounce: 0.1 }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------- numbers ---- */
export function Num({ value, className = "", prefix = "", suffix = "" }:
  { value: number; className?: string; prefix?: string; suffix?: string }) {
  return <NumberFlow value={value} className={`tabular ${className}`} prefix={prefix} suffix={suffix} />;
}

/* --------------------------------------------------------------- motion ---- */
const EASE = [0.2, 0.8, 0.2, 1] as const;

export function Stagger({ children, className = "", delay = 0 }:
  { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div className={className} initial="hidden" animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.055, delayChildren: delay } } }}>
      {children}
    </motion.div>
  );
}

export function Item({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className}
      variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } } }}>
      {children}
    </motion.div>
  );
}

/* ---------------------------------------------------------------- chrome ---- */
export function PageHeader({ title, subtitle, icon, action }:
  { title: string; subtitle?: string; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      {icon && (
        <div className="shrink-0 grid place-items-center h-11 w-11 rounded-2xl bg-primary-soft text-primary border border-primary-line/60 shadow-[var(--shadow-1)]">
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <h1 className="balance text-2xl font-extrabold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted font-semibold text-sm mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

/**
 * Cursor-following glow for `.spotlight` cards. Writes the pointer position straight into CSS
 * custom properties, so there is no React state and no re-render per pointermove.
 */
export function spotlight(e: React.PointerEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty("--mx", `${e.clientX - r.left}px`);
  el.style.setProperty("--my", `${e.clientY - r.top}px`);
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between mb-2.5">
      <h2 className="text-base font-extrabold tracking-tight">{children}</h2>
      {action}
    </div>
  );
}

export function StatTile({ label, value, sub, tone = "", icon }:
  { label: string; value: ReactNode; sub?: string; tone?: string; icon?: ReactNode }) {
  return (
    <div className="card lift-edge p-3.5">
      {icon && <div className="text-muted mb-1">{icon}</div>}
      <div className={`text-xl font-extrabold leading-none ${tone}`}>{value}</div>
      <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mt-1.5">{label}</div>
      {sub && <div className="text-[11px] font-semibold text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function Chip({ children, tone = "neutral", className = "" }:
  { children: ReactNode; tone?: "neutral" | "accent" | "primary" | "success" | "danger" | "info"; className?: string }) {
  const tones = {
    neutral: "bg-surface-2 text-ink-soft",
    accent: "bg-accent-soft text-accent-ink",
    primary: "bg-primary-soft text-primary",
    success: "bg-success-soft text-success",
    danger: "bg-danger-soft text-danger",
    info: "bg-info-soft text-info",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-extrabold ${tones[tone]} ${className}`}>{children}</span>;
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="rounded-xl bg-danger-soft text-danger px-3 py-2 text-sm font-semibold" role="alert">{message}</p>;
}

/* --------------------------------------------------------------- loading ---- */
export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-muted" role="status">
      <div className="h-8 w-8 rounded-full border-4 border-line border-t-primary animate-spin" />
      <span className="text-sm font-semibold">{label}</span>
    </div>
  );
}

export function SkeletonCard({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`card p-4 ${className}`}>
      <div className="skeleton h-4 w-1/3 mb-3" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-3 mb-2" style={{ width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}

export function SkeletonPage() {
  return (
    <div className="pt-2 flex flex-col gap-4" aria-busy="true">
      <div className="skeleton h-8 w-52" />
      <SkeletonCard lines={2} />
      <div className="grid grid-cols-2 gap-3">
        <SkeletonCard lines={2} /><SkeletonCard lines={2} />
      </div>
      <SkeletonCard lines={4} />
    </div>
  );
}

export function EmptyState({ icon, title, body, action }:
  { icon: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="card p-8 text-center flex flex-col items-center gap-2">
      <div className="text-3xl">{icon}</div>
      <p className="font-extrabold">{title}</p>
      <p className="text-sm text-muted font-semibold max-w-xs">{body}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------ loading + touch ---- */

/**
 * Loading state with rotating friendly copy (adapted from Kokonut UI's ai-text-loading,
 * re-tokened and rebuilt on the CSS shimmer). Use where a plain Spinner feels too blank.
 */
export function LoadingQuips({ quips, interval = 1800 }: { quips: string[]; interval?: number }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % quips.length), interval);
    return () => clearInterval(t);
  }, [interval, quips.length]);
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20" role="status" aria-live="polite">
      <div className="h-8 w-8 rounded-full border-4 border-line border-t-primary animate-spin" />
      <span key={i} className="shimmer-text pop-in text-sm font-extrabold">{quips[i]}</span>
    </div>
  );
}

/**
 * Press-and-hold confirmation button (adapted from Kokonut UI's hold-button, rebuilt on `.btn`).
 * The fill is a scaleX overlay, so the whole gesture stays on the compositor. Under reduced
 * motion a hold gesture with no visible progress would be baffling, so it completes on tap.
 */
export function HoldButton({ children, onComplete, holdMs = 900, className = "", disabled = false }: {
  children: ReactNode; onComplete: () => void; holdMs?: number; className?: string; disabled?: boolean;
}) {
  const still = useReducedMotion();
  const [holding, setHolding] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stop = () => {
    setHolding(false);
    if (timer.current) clearTimeout(timer.current);
  };
  const start = () => {
    if (disabled) return;
    if (still) { onComplete(); return; }
    setHolding(true);
    timer.current = setTimeout(() => { setHolding(false); onComplete(); }, holdMs);
  };
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  return (
    <button type="button" disabled={disabled}
      className={`btn relative overflow-clip touch-none select-none ${className}`}
      onPointerDown={start} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop}
      onContextMenu={(e) => e.preventDefault()}>
      <motion.span aria-hidden className="absolute inset-0 origin-left"
        style={{ background: "color-mix(in srgb, var(--primary-ink) 25%, transparent)" }}
        initial={{ scaleX: 0 }} animate={{ scaleX: holding ? 1 : 0 }}
        transition={holding ? { duration: holdMs / 1000, ease: "linear" } : { duration: 0.18 }} />
      <span className="relative inline-flex items-center gap-2">{children}</span>
    </button>
  );
}

/**
 * Concentric progress rings (adapted from Kokonut UI's apple-activity-card: same dashoffset
 * mechanics, our tokens, and no per-stroke drop-shadow filters — those are a jank source on
 * low-end phones). Rings render outermost first.
 */
export function ActivityRings({ rings, size = 120, stroke = 10, children }: {
  rings: { value: number; color: string; label: string }[];
  size?: number; stroke?: number; children?: ReactNode;
}) {
  const label = rings
    .map((r) => `${r.label}: ${Math.round(Math.min(1, Math.max(0, r.value)) * 100)}%`)
    .join(", ");
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} className="-rotate-90">
        {rings.map((ring, idx) => {
          const r = (size - stroke) / 2 - idx * (stroke + 3);
          const c = 2 * Math.PI * r;
          const pct = Math.min(1, Math.max(0, ring.value));
          return (
            <g key={ring.label}>
              <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
              <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={ring.color}
                strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c}
                initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - pct) }}
                transition={{ type: "spring", visualDuration: 0.9, bounce: 0, delay: idx * 0.12 }} />
            </g>
          );
        })}
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}
