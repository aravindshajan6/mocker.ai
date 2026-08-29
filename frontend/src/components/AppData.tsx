"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CurrentAffairs, Daily, ReviewDue, Stats, Topic, User } from "@/lib/types";

/**
 * One place that owns the small set of things nearly every screen needs (who you are, your stats,
 * what is due). Before this, each page refetched the same five endpoints on every navigation.
 */
type Data = {
  user: User | null;
  stats: Stats | null;
  daily: Daily | null;
  due: ReviewDue | null;
  ca: CurrentAffairs | null;
  topics: Topic[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const Ctx = createContext<Data | null>(null);

export function AppDataProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [daily, setDaily] = useState<Daily | null>(null);
  const [due, setDue] = useState<ReviewDue | null>(null);
  const [ca, setCa] = useState<CurrentAffairs | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [u, s, d, r, c, t] = await Promise.all([
        api.me(), api.stats(), api.daily(), api.reviewQueue(), api.currentAffairs(), api.topics(),
      ]);
      setUser(u); setStats(s); setDaily(d); setDue(r); setCa(c); setTopics(t);
      setError(null);
    } catch (e) {
      setError((e as Error)?.message || "Could not load your data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Deferred so the first paint isn't blocked by a synchronous state write in the effect body.
    const id = setTimeout(() => { if (!cancelled) void refresh(); }, 0);
    return () => { cancelled = true; clearTimeout(id); };
  }, [refresh]);

  const value = useMemo<Data>(
    () => ({ user, stats, daily, due, ca, topics, loading, error, refresh }),
    [user, stats, daily, due, ca, topics, loading, error, refresh]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppData(): Data {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAppData must be used inside AppDataProvider");
  return v;
}
