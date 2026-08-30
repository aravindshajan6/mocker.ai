"use client";

import { useState } from "react";
import { Newspaper, ShieldCheck } from "lucide-react";
import { ErrorNote, Item } from "@/components/ui";
import { api } from "@/lib/api";
import type { AdminOverview } from "@/lib/types";

export default function AdminContent({ overview, onChange }:
  { overview: AdminOverview | null; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (what: "news" | "audit", fn: () => Promise<{ detail: string }>) => {
    setBusy(what); setError(null); setNote(null);
    try {
      setNote((await fn()).detail);
      setTimeout(onChange, 2000);
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
