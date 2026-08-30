"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Clock, KeyRound, Trash2, XCircle } from "lucide-react";
import { ErrorNote, Item } from "@/components/ui";
import { api } from "@/lib/api";
import type { Credential } from "@/lib/types";

type Provider = { id: string; base_url: string; default_model: string; free_tier: boolean };

export default function AdminKeys({ onChange }: { onChange: () => void }) {
  const [keys, setKeys] = useState<Credential[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [envProvider, setEnvProvider] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | "add" | null>(null);
  const [form, setForm] = useState({ label: "", provider: "groq", api_key: "", model: "", priority: 100 });

  const load = async () => {
    try {
      const [k, p] = await Promise.all([api.adminKeys(), api.adminProviders()]);
      setKeys(k);
      setProviders(p.providers);
      setEnvProvider(p.env_key_present ? p.env_provider : "");
    } catch (e) {
      setError((e as Error)?.message || "Could not load keys.");
    }
  };
  useEffect(() => { const t = setTimeout(() => void load(), 0); return () => clearTimeout(t); }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("add"); setError(null); setNote(null);
    try {
      await api.adminAddKey(form);
      setForm({ label: "", provider: form.provider, api_key: "", model: "", priority: 100 });
      setNote("Key added. Test it to make sure it works.");
      await load();
      onChange();
    } catch (err) {
      setError((err as Error)?.message || "Could not add that key.");
    } finally {
      setBusy(null);
    }
  };

  const act = async (id: number, fn: () => Promise<unknown>) => {
    setBusy(id); setError(null); setNote(null);
    try {
      const r = await fn() as { ok?: boolean; detail?: string; latency_ms?: number | null };
      if (r && "ok" in r && "detail" in r) {
        setNote(r.ok ? `Working — replied in ${r.latency_ms}ms` : `Failed: ${r.detail}`);
      }
      await load();
      onChange();
    } catch (e) {
      setError((e as Error)?.message || "That didn't work.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <ErrorNote message={error} />
      {note && <Item><p className="rounded-xl bg-success-soft text-success px-3 py-2 text-sm font-bold">{note}</p></Item>}

      <Item>
        <div className="card p-4">
          <p className="font-extrabold">How keys are used</p>
          <p className="text-xs text-muted font-semibold mt-1 leading-relaxed">
            Keys are tried in priority order, lowest number first. A key the provider rejects is switched off
            automatically; a rate-limited one rests for six hours and the next key takes over. So when a free tier
            runs out, add another here and generation carries on without a redeploy.
            {envProvider && <> An environment key (<b>{envProvider}</b>) is used as a last resort.</>}
          </p>
        </div>
      </Item>

      {keys.map((k) => (
        <Item key={k.id}>
          <div className="card p-4">
            <div className="flex items-start gap-3">
              <div className={`grid place-items-center h-10 w-10 rounded-2xl shrink-0
                ${!k.is_active ? "bg-danger-soft text-danger" : k.cooling_down ? "bg-accent-soft text-accent-ink" : "bg-success-soft text-success"}`}>
                {!k.is_active ? <XCircle size={18} /> : k.cooling_down ? <Clock size={18} /> : <CheckCircle2 size={18} />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-extrabold truncate">{k.label}</p>
                <p className="text-xs text-muted font-semibold">
                  {k.provider} · {k.model || "default model"} · priority {k.priority}
                </p>
                <p className="text-[11px] font-mono text-muted mt-0.5">{k.api_key_masked}</p>
                <p className="text-[11px] font-semibold mt-1">
                  {!k.is_active ? <span className="text-danger">Disabled — the provider rejected it</span>
                    : k.cooling_down ? <span className="text-accent-ink">Rate limited, resting until {new Date(k.cooldown_until!).toLocaleTimeString()}</span>
                    : <span className="text-success">Active</span>}
                  {k.last_used_at && <span className="text-muted"> · last used {new Date(k.last_used_at).toLocaleString()}</span>}
                </p>
                {k.last_error && <p className="text-[11px] text-danger font-semibold mt-1 line-clamp-2">{k.last_error}</p>}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <button className="btn btn-ghost !min-h-10 text-xs px-3" disabled={busy !== null}
                onClick={() => act(k.id, () => api.adminTestKey(k.id))}>Test</button>
              <button className="btn btn-ghost !min-h-10 text-xs px-3" disabled={busy !== null}
                onClick={() => act(k.id, () => api.adminPatchKey(k.id, { is_active: !k.is_active, clear_cooldown: true }))}>
                {k.is_active ? "Disable" : "Enable"}
              </button>
              {k.cooling_down && (
                <button className="btn btn-ghost !min-h-10 text-xs px-3" disabled={busy !== null}
                  onClick={() => act(k.id, () => api.adminPatchKey(k.id, { clear_cooldown: true }))}>Clear cooldown</button>
              )}
              <button className="btn btn-quiet !min-h-10 text-xs px-3 text-danger" disabled={busy !== null}
                onClick={() => act(k.id, () => api.adminDeleteKey(k.id))}>
                <Trash2 size={13} /> Remove
              </button>
            </div>
          </div>
        </Item>
      ))}

      <Item>
        <form onSubmit={add} className="card p-4 flex flex-col gap-3">
          <p className="font-extrabold flex items-center gap-2"><KeyRound size={16} /> Add a key</p>
          <input className="field" placeholder="Label (e.g. Groq — spare)" required maxLength={80}
            value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <div className="flex gap-2">
            <select className="field flex-1" value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.id}{p.free_tier ? " (free tier)" : ""}</option>
              ))}
            </select>
            <input className="field w-28" type="number" min={0} max={1000} value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} aria-label="Priority" />
          </div>
          <input className="field font-mono text-sm" placeholder="API key" required minLength={8}
            value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          <input className="field" placeholder={`Model (optional — defaults to ${providers.find((p) => p.id === form.provider)?.default_model ?? ""})`}
            value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
          <button className="btn btn-primary" disabled={busy !== null}>{busy === "add" ? "Adding…" : "Add key"}</button>
          <p className="text-[11px] text-muted font-semibold">
            Free options: Groq (console.groq.com), Google Gemini (aistudio.google.com), OpenRouter, or a local
            Ollama. Keys are stored server-side and only ever shown masked.
          </p>
        </form>
      </Item>
    </>
  );
}
