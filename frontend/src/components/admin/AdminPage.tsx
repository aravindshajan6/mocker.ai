"use client";

import { useEffect, useState } from "react";
import { Database, KeyRound, PlusCircle, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { useAppData } from "@/components/AppData";
import { ErrorNote, Item, PageHeader, SkeletonPage, Stagger } from "@/components/ui";
import AdminContent from "./AdminContent";
import AdminKeys from "./AdminKeys";
import AdminQuestions from "./AdminQuestions";
import AdminUsers from "./AdminUsers";
import { api } from "@/lib/api";
import type { AdminOverview } from "@/lib/types";

const TABS = [
  { id: "content", label: "Content", icon: RefreshCw },
  { id: "questions", label: "Questions", icon: PlusCircle },
  { id: "keys", label: "API keys", icon: KeyRound },
  { id: "users", label: "Accounts", icon: Users },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AdminPage() {
  const { user, loading } = useAppData();
  const [tab, setTab] = useState<TabId>("content");
  const [ov, setOv] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.adminOverview().then(setOv).catch((e: Error) => setError(e?.message || "Could not load."));
  useEffect(() => {
    const id = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(id);
  }, []);

  if (loading) return <SkeletonPage />;
  if (user && !user.is_admin) {
    return (
      <div className="pt-16 text-center flex flex-col items-center gap-2">
        <ShieldCheck size={36} className="text-muted" />
        <p className="font-extrabold">Administrators only</p>
        <p className="text-sm text-muted font-semibold">This area manages content and accounts.</p>
      </div>
    );
  }

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <PageHeader title="Admin" icon={<ShieldCheck size={20} />}
          subtitle="Content, questions, provider keys and accounts." />
      </Item>

      <ErrorNote message={error} />

      {ov && (
        <Item>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Tile icon={<Database size={14} />} label="Questions" value={ov.questions_active.toLocaleString()} />
            <Tile icon={<Users size={14} />} label="Accounts" value={`${ov.users}`} sub={`${ov.admins} admin`} />
            <Tile icon={<KeyRound size={14} />} label="LLM keys" value={`${ov.llm_keys_active}`}
              sub={ov.llm_available ? "available" : "none working"}
              tone={ov.llm_available ? "text-success" : "text-danger"} />
            <Tile icon={<ShieldCheck size={14} />} label="Audited" value={`${ov.audit.checked}`}
              sub={`${ov.audit.remaining} to go`} />
          </div>
        </Item>
      )}

      <Item>
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-1.5 text-xs font-extrabold px-3 py-2 rounded-xl whitespace-nowrap transition
                  ${tab === t.id ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted hover:text-ink"}`}>
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>
      </Item>

      {tab === "content" && <AdminContent overview={ov} onChange={refresh} />}
      {tab === "questions" && <AdminQuestions onChange={refresh} />}
      {tab === "keys" && <AdminKeys onChange={refresh} />}
      {tab === "users" && <AdminUsers onChange={refresh} />}
    </Stagger>
  );
}

function Tile({ icon, label, value, sub, tone = "" }:
  { icon: React.ReactNode; label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="card p-3.5">
      <div className="text-muted mb-1">{icon}</div>
      <div className={`text-xl font-extrabold leading-none ${tone}`}>{value}</div>
      <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mt-1.5">{label}</div>
      {sub && <div className="text-[11px] font-semibold text-muted mt-0.5">{sub}</div>}
    </div>
  );
}
