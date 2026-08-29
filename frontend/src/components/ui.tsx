"use client";

export function ProgressBar({ value, className = "", color = "var(--primary)" }: { value: number; className?: string; color?: string }) {
  return (
    <div className={`h-2.5 w-full rounded-full bg-surface-2 overflow-hidden ${className}`} role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: `${Math.min(100, Math.max(0, value * 100))}%`, background: color }} />
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-muted" role="status">
      <div className="h-8 w-8 rounded-full border-4 border-line border-t-primary animate-spin" />
      <span className="text-sm font-semibold">{label}</span>
    </div>
  );
}

export function Chip({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "primary" | "success" | "danger" }) {
  const tones = {
    neutral: "bg-surface-2 text-ink",
    accent: "bg-accent-soft text-ink",
    primary: "bg-primary-soft text-primary",
    success: "bg-success-soft text-success",
    danger: "bg-danger-soft text-danger",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-extrabold ${tones[tone]}`}>{children}</span>;
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="rounded-xl bg-danger-soft text-danger px-3 py-2 text-sm font-semibold" role="alert">{message}</p>;
}
