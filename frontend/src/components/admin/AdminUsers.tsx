"use client";

import { useEffect, useMemo, useState } from "react";
import { Flame, KeyRound, Trash2, UserPlus } from "lucide-react";
import { ErrorNote, Item } from "@/components/ui";
import AdminAnalytics, { fmtDuration } from "./AdminAnalytics";
import { api } from "@/lib/api";
import type { AdminUserRow } from "@/lib/types";

function fmtAgo(iso: string | null): string {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  const days = Math.round(hrs / 24);
  return days < 30 ? `${days} day${days === 1 ? "" : "s"} ago`
    : new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

const SORTS = {
  seen: { label: "Last seen", key: (u: AdminUserRow) => (u.last_seen_at ? new Date(u.last_seen_at).getTime() : 0) },
  screen: { label: "Screen time", key: (u: AdminUserRow) => u.screen_seconds_total },
  answered: { label: "Answered", key: (u: AdminUserRow) => u.answered },
  newest: { label: "Newest", key: (u: AdminUserRow) => new Date(u.created_at).getTime() },
} as const;
type SortId = keyof typeof SORTS;

export default function AdminUsers({ onChange }: { onChange: () => void }) {
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", is_admin: false });
  const [sort, setSort] = useState<SortId>("seen");
  const sorted = useMemo(() => [...rows].sort((a, b) => SORTS[sort].key(b) - SORTS[sort].key(a)), [rows, sort]);

  const load = () => api.adminUsers().then(setRows).catch((e: Error) => setError(e?.message || "Could not load accounts."));
  useEffect(() => { const t = setTimeout(() => void load(), 0); return () => clearTimeout(t); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null); setNote(null);
    try {
      const u = await api.adminCreateUser(form);
      setNote(`Created ${u.email}. Share the password with them directly — it is not shown again.`);
      setForm({ name: "", email: "", password: "", is_admin: false });
      load(); onChange();
    } catch (err) {
      setError((err as Error)?.message || "Could not create that account.");
    } finally {
      setBusy(false);
    }
  };

  const reset = async (u: AdminUserRow) => {
    const pw = prompt(`New password for ${u.email} (at least 6 characters)`);
    if (!pw) return;
    try {
      await api.adminResetPassword(u.id, pw);
      setNote(`Password updated for ${u.email}.`);
    } catch (e) {
      setError((e as Error)?.message || "Could not reset that password.");
    }
  };

  const remove = async (u: AdminUserRow) => {
    if (!confirm(`Delete ${u.email}? Their answers and progress go too. This cannot be undone.`)) return;
    try {
      await api.adminDeleteUser(u.id);
      load(); onChange();
    } catch (e) {
      setError((e as Error)?.message || "Could not delete that account.");
    }
  };

  return (
    <>
      <AdminAnalytics />
      <ErrorNote message={error} />
      {note && <Item><p className="rounded-xl bg-success-soft text-success px-3 py-2 text-sm font-bold">{note}</p></Item>}

      <Item>
        <div className="card p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-extrabold">Accounts ({rows.length})</p>
              <p className="text-xs text-muted font-semibold mt-0.5">
                Public sign-up is closed, so every account is created here.
              </p>
            </div>
            <label className="flex items-center gap-1.5 text-[11px] font-extrabold text-muted shrink-0">
              Sort
              <select className="rounded-lg border border-line bg-surface px-2 py-1 text-xs font-bold text-ink"
                value={sort} onChange={(e) => setSort(e.target.value as SortId)}>
                {Object.entries(SORTS).map(([id, s]) => <option key={id} value={id}>{s.label}</option>)}
              </select>
            </label>
          </div>
          <div className="mt-3 flex flex-col gap-2">
            {sorted.map((u) => (
              <div key={u.id} className="flex items-center gap-3 py-2 border-t border-line first:border-0">
                <div className="flex-1 min-w-0">
                  <p className="font-extrabold text-sm truncate">
                    {u.name}
                    {u.is_admin && <span className="ml-1.5 rounded-full bg-primary-soft text-primary px-1.5 py-0.5 text-[10px]">admin</span>}
                  </p>
                  <p className="text-[11px] text-muted font-semibold truncate">{u.email}</p>
                  <p className="text-[11px] text-muted font-semibold">
                    Last seen {fmtAgo(u.last_seen_at)} · joined {new Date(u.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {[
                      `${fmtDuration(u.screen_seconds_total)} total`,
                      `${fmtDuration(u.screen_seconds_week)} this week`,
                      `${u.active_days_month} of 30 days active`,
                      `${u.answered} answered`,
                      ...(u.accuracy !== null ? [`${Math.round(u.accuracy * 100)}% correct`] : []),
                      `${u.quizzes_completed} quizzes`,
                    ].map((t) => (
                      <span key={t} className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-bold text-ink-soft">{t}</span>
                    ))}
                    {u.current_streak > 0 && (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-bold text-accent-ink">
                        <Flame size={10} /> {u.current_streak}
                      </span>
                    )}
                  </div>
                </div>
                <button className="btn btn-quiet !min-h-9 text-xs px-2" onClick={() => reset(u)} title="Reset password">
                  <KeyRound size={14} />
                </button>
                <button className="btn btn-quiet !min-h-9 text-xs px-2 text-danger" onClick={() => remove(u)} title="Delete account">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </Item>

      <Item>
        <form onSubmit={create} className="card p-4 flex flex-col gap-3">
          <p className="font-extrabold flex items-center gap-2"><UserPlus size={16} /> Create an account</p>
          <input className="field" placeholder="Name" required maxLength={80}
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="field" type="email" placeholder="Email" required
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input className="field" placeholder="Temporary password (min 6 characters)" required minLength={6}
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <label className="flex items-center gap-2 text-sm font-bold">
            <input type="checkbox" checked={form.is_admin}
              onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} />
            Give this account administrator access
          </label>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        </form>
      </Item>
    </>
  );
}
