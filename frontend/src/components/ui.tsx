"use client";

import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

/* ------------------------------------------------------------------ bars ---- */
export function ProgressBar({ value, className = "", color = "var(--primary)" }:
  { value: number; className?: string; color?: string }) {
  const pct = Math.min(100, Math.max(0, value * 100));
  return (
    <div className={`h-2.5 w-full rounded-full bg-surface-2 overflow-hidden ${className}`}
      role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <motion.div className="h-full rounded-full" style={{ background: color }}
        initial={{ width: 0 }} animate={{ width: `${pct}%` }}
        transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }} />
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
          transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }} />
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
      {icon && <div className="shrink-0 grid place-items-center h-11 w-11 rounded-2xl bg-primary-soft text-primary">{icon}</div>}
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl font-extrabold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted font-semibold text-sm mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
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
    <div className="card p-3.5">
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
