"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BookOpenCheck, Search, Shuffle } from "lucide-react";
import { useAppData } from "@/components/AppData";
import { Item, PageHeader, ProgressBar, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";

export default function Practice() {
  const router = useRouter();
  const { topics, loading, error } = useAppData();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? topics.filter((t) => (t.name + t.description).toLowerCase().includes(needle)) : topics;
  }, [topics, q]);

  const mixed = async () => {
    setBusy(true);
    try {
      const s = await api.startQuiz({ mode: "mixed" });
      router.push(`/quiz/${s.id}`);
    } catch { setBusy(false); }
  };

  if (error) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
  if (loading) return <SkeletonPage />;

  return (
    <Stagger className="pt-1">
      <Item>
        <PageHeader title="Practise by topic" icon={<BookOpenCheck size={20} />}
          subtitle="Pick a subject, or let us mix it up for you." />
      </Item>

      <Item>
        <div className="flex gap-2 mb-4">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input className="field !pl-10" placeholder="Search topics" value={q}
              onChange={(e) => setQ(e.target.value)} aria-label="Search topics" />
          </div>
          <button className="btn btn-ghost !min-h-[3.1rem] px-4 shrink-0" onClick={mixed} disabled={busy}>
            <Shuffle size={16} /> {busy ? "…" : "Mixed"}
          </button>
        </div>
      </Item>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {filtered.map((t) => {
          const pct = t.question_count ? t.answered / t.question_count : 0;
          return (
            <Item key={t.slug}>
              <Link href={`/practice/${t.slug}`} className="card card-interactive p-4 flex gap-3.5 h-full">
                <span className="text-2xl shrink-0">{t.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-extrabold leading-tight">{t.name}</p>
                  <p className="text-xs text-muted font-semibold mt-0.5 line-clamp-2">{t.description}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <ProgressBar value={pct} className="!h-1.5 flex-1"
                      color={t.accuracy !== null && t.accuracy < 0.5 ? "var(--danger)" : "var(--primary)"} />
                    <span className="text-[10px] font-extrabold text-muted tabular shrink-0">
                      {t.answered}/{t.question_count}
                    </span>
                  </div>
                  {t.accuracy !== null && (
                    <p className="text-[11px] font-extrabold text-muted mt-1">{Math.round(t.accuracy * 100)}% accuracy so far</p>
                  )}
                </div>
              </Link>
            </Item>
          );
        })}
      </div>
      {filtered.length === 0 && <p className="text-center text-muted font-semibold py-10">No topic matches “{q}”.</p>}
    </Stagger>
  );
}
