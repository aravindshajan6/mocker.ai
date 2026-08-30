"use client";

import { useCallback, useEffect, useState } from "react";
import { Eye, EyeOff, PlusCircle, Search } from "lucide-react";
import { useAppData } from "@/components/AppData";
import { ErrorNote, Item } from "@/components/ui";
import { api } from "@/lib/api";
import type { AdminQuestion } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];
const PAGE = 15;
const empty = { question: "", options: ["", "", "", ""], answer: 0, explanation: "", difficulty: 2, tags: "" };

export default function AdminQuestions({ onChange }: { onChange: () => void }) {
  const { topics } = useAppData();
  const [rows, setRows] = useState<AdminQuestion[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [only, setOnly] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ ...empty, topic: "" });

  const load = useCallback(async (search: string, filter: string, off: number) => {
    try {
      const r = await api.adminQuestions({ q: search, only: filter, limit: PAGE, offset: off });
      setRows(r.questions);
      setTotal(r.total);
    } catch (e) {
      setError((e as Error)?.message || "Could not load questions.");
    }
  }, []);
  useEffect(() => { const t = setTimeout(() => void load("", "all", 0), 0); return () => clearTimeout(t); }, [load]);

  const search = (e: React.FormEvent) => { e.preventDefault(); setOffset(0); void load(q, only, 0); };
  const filter = (f: string) => { setOnly(f); setOffset(0); void load(q, f, 0); };
  const page = (o: number) => { setOffset(o); void load(q, only, o); };

  const toggle = async (row: AdminQuestion) => {
    try {
      await api.adminToggleQuestion(row.id);
      void load(q, only, offset);
      onChange();
    } catch (e) {
      setError((e as Error)?.message || "Could not change that question.");
    }
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null); setNote(null);
    try {
      await api.adminAddQuestion({
        topic: form.topic || topics[0]?.slug,
        question: form.question,
        options: form.options,
        answer: form.answer,
        explanation: form.explanation,
        difficulty: form.difficulty,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setNote("Question added and live.");
      setForm({ ...empty, topic: form.topic });
      setAdding(false);
      void load(q, only, 0);
      onChange();
    } catch (err) {
      setError((err as Error)?.message || "Could not add that question.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <ErrorNote message={error} />
      {note && <Item><p className="rounded-xl bg-success-soft text-success px-3 py-2 text-sm font-bold">{note}</p></Item>}

      <Item>
        <button className="btn btn-primary w-full" onClick={() => setAdding((v) => !v)}>
          <PlusCircle size={16} /> {adding ? "Cancel" : "Add a question"}
        </button>
      </Item>

      {adding && (
        <Item>
          <form onSubmit={create} className="card p-4 flex flex-col gap-3">
            <select className="field" value={form.topic || topics[0]?.slug || ""}
              onChange={(e) => setForm({ ...form, topic: e.target.value })}>
              {topics.map((t) => <option key={t.slug} value={t.slug}>{t.icon} {t.name}</option>)}
            </select>
            <textarea className="field" rows={2} placeholder="Question" required minLength={10} maxLength={600}
              value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} />
            {form.options.map((o, i) => (
              <label key={i} className="flex items-center gap-2">
                <input type="radio" name="answer" checked={form.answer === i}
                  onChange={() => setForm({ ...form, answer: i })} aria-label={`Option ${LETTERS[i]} is correct`} />
                <span className="text-xs font-extrabold text-muted w-4">{LETTERS[i]}</span>
                <input className="field flex-1" placeholder={`Option ${LETTERS[i]}`} required value={o}
                  onChange={(e) => {
                    const next = [...form.options];
                    next[i] = e.target.value;
                    setForm({ ...form, options: next });
                  }} />
              </label>
            ))}
            <p className="text-[11px] text-muted font-semibold">Select the radio button next to the correct option.</p>
            <textarea className="field" rows={2} placeholder="Explanation shown after answering" maxLength={1200}
              value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} />
            <div className="flex gap-2">
              <select className="field flex-1" value={form.difficulty}
                onChange={(e) => setForm({ ...form, difficulty: Number(e.target.value) })}>
                <option value={1}>Easy</option><option value={2}>Medium</option><option value={3}>Hard</option>
              </select>
              <input className="field flex-1" placeholder="Tags, comma separated" value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })} />
            </div>
            <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Add question"}</button>
          </form>
        </Item>
      )}

      <Item>
        <form onSubmit={search} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input className="field !pl-10" placeholder="Search question text" value={q}
              onChange={(e) => setQ(e.target.value)} />
          </div>
          <button className="btn btn-ghost !min-h-[3.1rem] px-4">Search</button>
        </form>
      </Item>

      <Item>
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {[["all", "All"], ["active", "Live"], ["inactive", "Retired"], ["flagged", "Flagged by audit"]].map(([f, label]) => (
            <button key={f} onClick={() => filter(f)}
              className={`text-xs font-extrabold px-3 py-1.5 rounded-xl whitespace-nowrap ${only === f ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted"}`}>
              {label}
            </button>
          ))}
        </div>
      </Item>

      {rows.map((row) => (
        <Item key={row.id}>
          <div className={`card p-4 ${row.is_active ? "" : "opacity-70"}`}>
            <div className="flex items-center justify-between text-[11px] font-extrabold text-muted mb-1">
              <span>#{row.id} · {row.topic} · {row.source}</span>
              <span>{row.times_answered} answers</span>
            </div>
            <p className="font-extrabold leading-snug">{row.text}</p>
            <div className="mt-2 flex flex-col gap-1">
              {row.options.map((o, i) => (
                <p key={i} className={`text-sm font-semibold ${i === row.correct_index ? "text-success" : "text-muted"}`}>
                  {i === row.correct_index ? "✓" : LETTERS[i]} {o}
                </p>
              ))}
            </div>
            {row.verdict && row.verdict !== "ok" && (
              <p className="text-[11px] font-bold text-danger mt-2">Audit: {row.verdict} — {row.verdict_note}</p>
            )}
            <button className="btn btn-ghost !min-h-9 text-xs px-3 mt-3" onClick={() => toggle(row)}>
              {row.is_active ? <><EyeOff size={13} /> Retire</> : <><Eye size={13} /> Bring back</>}
            </button>
          </div>
        </Item>
      ))}

      {total > PAGE && (
        <Item>
          <div className="flex items-center justify-between">
            <button className="btn btn-ghost !min-h-10 text-sm" disabled={offset === 0}
              onClick={() => page(Math.max(0, offset - PAGE))}>← Previous</button>
            <span className="text-xs font-extrabold text-muted">
              {offset + 1}–{Math.min(offset + PAGE, total)} of {total.toLocaleString()}
            </span>
            <button className="btn btn-ghost !min-h-10 text-sm" disabled={offset + PAGE >= total}
              onClick={() => page(offset + PAGE)}>Next →</button>
          </div>
        </Item>
      )}
    </>
  );
}
