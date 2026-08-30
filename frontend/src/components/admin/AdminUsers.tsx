"use client";

import { useEffect, useState } from "react";
import { KeyRound, Trash2, UserPlus } from "lucide-react";
import { ErrorNote, Item } from "@/components/ui";
import { api } from "@/lib/api";
import type { AdminUserRow } from "@/lib/types";

export default function AdminUsers({ onChange }: { onChange: () => void }) {
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", is_admin: false });

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
      <ErrorNote message={error} />
      {note && <Item><p className="rounded-xl bg-success-soft text-success px-3 py-2 text-sm font-bold">{note}</p></Item>}

      <Item>
        <div className="card p-4">
          <p className="font-extrabold">Accounts ({rows.length})</p>
          <p className="text-xs text-muted font-semibold mt-0.5">
            Public sign-up is closed, so every account is created here.
          </p>
          <div className="mt-3 flex flex-col gap-2">
            {rows.map((u) => (
              <div key={u.id} className="flex items-center gap-3 py-2 border-t border-line first:border-0">
                <div className="flex-1 min-w-0">
                  <p className="font-extrabold text-sm truncate">
                    {u.name}
                    {u.is_admin && <span className="ml-1.5 rounded-full bg-primary-soft text-primary px-1.5 py-0.5 text-[10px]">admin</span>}
                  </p>
                  <p className="text-[11px] text-muted font-semibold truncate">{u.email}</p>
                  <p className="text-[11px] text-muted font-semibold">
                    {u.answered} answered{u.last_active ? ` · last active ${u.last_active}` : " · never signed in"}
                  </p>
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
