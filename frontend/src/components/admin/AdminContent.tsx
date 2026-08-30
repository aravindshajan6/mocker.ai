"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Newspaper, ShieldCheck } from "lucide-react";
import { ErrorNote, Item } from "@/components/ui";
import { api } from "@/lib/api";
import type { AdminOverview, ContentHealth } from "@/lib/types";

export default function AdminContent({ overview, onChange }:
  { overview: AdminOverview | null; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [health, setHealth] = useState<ContentHealth | null>(null);

  const loadHealth = useCallback(() => api.adminContentHealth().then(setHealth).catch(() => {}), []);
  useEffect(() => { const t = setTimeout(() => void loadHealth(), 0); return () => clearTimeout(t); }, [loadHealth]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (what: "news" | "audit", fn: () => Promise<{ detail: string }>) => {
    setBusy(what); setError(null); setNote(null);
    try {
      setNote((await fn()).detail);
      setTimeout(() => { onChange(); void loadHealth(); }, 2000);
    } catch (e) {
      setError((e as Error)?.message || "That job could not be started.");
    } finally {
      setBusy(null);
    }
  };

  const last = overview?.last_content_run;

  return (
    <>
      <ErrorNote message={error} />
      {note && <Item><p className="rounded-xl bg-success-soft text-success px-3 py-2 text-sm font-bold">{note}</p></Item>}

      {health && <Item><HealthPanel health={health} /></Item>}

      <Item>
        <div className="card p-4">
          <div className="flex items-start gap-3">
            <div className="grid place-items-center h-10 w-10 rounded-2xl bg-accent-soft text-accent-ink shrink-0">
              <Newspaper size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-extrabold">Fetch today&apos;s news</p>
              <p className="text-xs text-muted font-semibold mt-0.5 leading-relaxed">
                Reads the news feeds and writes fresh current-affairs questions. Runs automatically at 06:00 IST;
                this is for pulling them in early or after a failed run.
              </p>
              {last && (
                <p className="text-[11px] font-semibold text-muted mt-2">
                  Last run {last.day} · {last.status} · {last.provider} · fetched {last.fetched}, generated{" "}
                  {last.generated}, added {last.inserted}
                  {last.error ? ` · ${last.error}` : ""}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button className="btn btn-primary flex-1 !min-h-11" disabled={busy !== null}
              onClick={() => run("news", () => api.adminRunNews(false))}>
              {busy === "news" ? "Starting…" : "Fetch now"}
            </button>
            <button className="btn btn-ghost !min-h-11 px-4" disabled={busy !== null}
              onClick={() => run("news", () => api.adminRunNews(true))}>
              Force re-run
            </button>
          </div>
        </div>
      </Item>

      <Item>
        <div className="card p-4">
          <div className="flex items-start gap-3">
            <div className="grid place-items-center h-10 w-10 rounded-2xl bg-info-soft text-info shrink-0">
              <ShieldCheck size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-extrabold">Audit imported answer keys</p>
              <p className="text-xs text-muted font-semibold mt-0.5 leading-relaxed">
                Checks bulk-imported questions and retires ones with a wrong answer. Runs nightly at 03:00 IST.
              </p>
              {overview && (
                <p className="text-[11px] font-semibold text-muted mt-2">
                  {overview.audit.checked} of {overview.audit.audited_pool} checked ·{" "}
                  {overview.audit.deactivated} retired · {overview.audit.flagged_for_review} flagged for review
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            {[25, 100, 400].map((n) => (
              <button key={n} className="btn btn-ghost flex-1 !min-h-11" disabled={busy !== null}
                onClick={() => run("audit", () => api.adminRunAudit(n))}>
                {busy === "audit" ? "…" : `Audit ${n}`}
              </button>
            ))}
          </div>
        </div>
      </Item>

      {overview && (
        <Item>
          <div className="card p-4">
            <p className="font-extrabold mb-2">Bank composition</p>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {Object.entries(overview.questions_by_source).sort((a, b) => b[1] - a[1]).map(([src, n]) => (
                <span key={src} className="rounded-full bg-surface-2 px-2.5 py-1 text-[11px] font-extrabold text-ink-soft">
                  {src}: {n.toLocaleString()}
                </span>
              ))}
            </div>
            <div className="flex flex-col gap-1">
              {overview.questions_by_topic.map((t) => (
                <div key={t.slug} className="flex justify-between text-xs font-bold">
                  <span>{t.icon} {t.name}</span>
                  <span className="text-muted tabular">{t.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </Item>
      )}
    </>
  );
}


function HealthPanel({ health }: { health: ContentHealth }) {
  const t = health.today;
  const tone = t.healthy
    ? { border: "border-success/40", chip: "bg-success-soft text-success" }
    : t.exhausted
      ? { border: "border-danger/40", chip: "bg-danger-soft text-danger" }
      : { border: "border-accent/40", chip: "bg-accent-soft text-accent-ink" };
  const Icon = t.healthy ? CheckCircle2 : t.exhausted ? AlertTriangle : Clock;
  const headline = t.healthy
    ? `Today is done — ${t.questions} questions published.`
    : t.exhausted
      ? `Today failed after ${t.attempts} attempts and has given up.`
      : t.attempts === 0
        ? "Today's pull hasn't run yet."
        : `Attempt ${t.attempts} failed. A retry is scheduled.`;

  return (
    <div className={`card p-4 ${tone.border}`}>
      <div className="flex items-start gap-3">
        <div className={`grid place-items-center h-10 w-10 rounded-2xl shrink-0 ${tone.chip}`}>
          <Icon size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-extrabold">{headline}</p>
          <p className="text-xs text-muted font-semibold mt-0.5 leading-relaxed">
            Scheduled for {String(health.scheduled_hour_ist).padStart(2, "0")}:00 IST. A day counts as done once it
            has at least {health.min_questions} questions; below that it retries on a widening backoff, up to{" "}
            {health.max_attempts} attempts.
          </p>
          <p className="text-xs font-semibold mt-1.5">
            <span className="text-muted">Right now: </span>
            <span className={health.due_now ? "text-accent-ink" : "text-ink-soft"}>{health.reason}</span>
          </p>
          {t.last_message && <p className="text-[11px] text-muted font-semibold mt-1">Last attempt: {t.last_message}</p>}
          {t.next_retry_at && !t.healthy && (
            <p className="text-[11px] font-extrabold text-accent-ink mt-1">
              Next retry {new Date(t.next_retry_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      <div className="flex gap-1 mt-3">
        {[...health.recent].reverse().map((d) => (
          <div key={d.day} className="flex-1 text-center" title={`${d.day}: ${d.questions} questions, ${d.attempts} attempt(s)`}>
            <div className={`h-8 rounded-lg ${d.healthy ? "bg-success" : d.attempts > 0 ? "bg-danger" : "bg-surface-3"}`} />
            <div className="text-[9px] font-extrabold text-muted mt-1">{d.day.slice(8)}</div>
          </div>
        ))}
      </div>
      <p className="text-[10px] font-semibold text-muted mt-1.5 text-center">Last {health.recent.length} days — green means questions were published.</p>
    </div>
  );
}
