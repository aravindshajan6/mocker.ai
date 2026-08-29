"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Play } from "lucide-react";
import { useAppData } from "@/components/AppData";
import { ErrorNote, Item, ProgressRing, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";

const SIZES = [5, 10, 20];

export default function TopicDetail({ slug }: { slug: string }) {
  const router = useRouter();
  const { topics, loading } = useAppData();
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const topic = topics.find((t) => t.slug === slug);

  const start = async (count: number) => {
    setBusy(count);
    setError(null);
    try {
      const s = await api.startQuiz({ mode: "topic", topic: slug, count });
      router.push(`/quiz/${s.id}`);
    } catch (e) {
      setError((e as Error)?.message || "Could not start that set.");
      setBusy(null);
    }
  };

  if (loading) return <SkeletonPage />;
  if (!topic) return (
    <div className="pt-10 text-center">
      <p className="font-bold">That topic doesn&apos;t exist.</p>
      <Link href="/practice" className="btn btn-ghost mt-4">Back to topics</Link>
    </div>
  );

  const pct = topic.question_count ? topic.answered / topic.question_count : 0;

  return (
    <Stagger className="pt-1 flex flex-col gap-4">
      <Item>
        <Link href="/practice" className="inline-flex items-center gap-1.5 text-sm font-extrabold text-muted hover:text-ink">
          <ArrowLeft size={16} /> Topics
        </Link>
      </Item>

      <Item>
        <div className="card p-5 flex items-center gap-4">
          <span className="text-4xl">{topic.icon}</span>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-extrabold leading-tight">{topic.name}</h1>
            <p className="text-sm text-muted font-semibold mt-0.5">{topic.description}</p>
          </div>
          <ProgressRing value={pct} size={72}>
            <div className="text-center leading-none">
              <div className="text-sm font-extrabold">{Math.round(pct * 100)}%</div>
              <div className="text-[9px] font-extrabold text-muted mt-0.5">SEEN</div>
            </div>
          </ProgressRing>
        </div>
      </Item>

      <Item>
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Questions" value={topic.question_count.toLocaleString()} />
          <Stat label="Answered" value={topic.answered.toLocaleString()} />
          <Stat label="Accuracy" value={topic.accuracy !== null ? `${Math.round(topic.accuracy * 100)}%` : "—"} />
        </div>
      </Item>

      <ErrorNote message={error} />

      <Item>
        <div className="card p-4">
          <p className="font-extrabold mb-3">Start a set</p>
          <div className="grid grid-cols-3 gap-2">
            {SIZES.map((n) => (
              <button key={n} className={n === 10 ? "btn btn-primary" : "btn btn-ghost"}
                onClick={() => start(n)} disabled={busy !== null}>
                {busy === n ? "…" : <><Play size={15} /> {n}</>}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted font-semibold mt-3">
            You&apos;ll get questions you haven&apos;t seen before first, then ones you last answered longest ago.
          </p>
        </div>
      </Item>
    </Stagger>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-3 text-center">
      <div className="text-lg font-extrabold">{value}</div>
      <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  );
}
