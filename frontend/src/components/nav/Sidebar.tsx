"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Compass, Flame, LogOut, Sparkles } from "lucide-react";
import Mascot from "@/components/Mascot";
import { startTour } from "@/components/Tour";
import ThemeToggle from "@/components/ThemeToggle";
import { useAppData } from "@/components/AppData";
import { NAV_GROUPS } from "./links";
import { api } from "@/lib/api";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { stats, due, user } = useAppData();

  const logout = async () => {
    await api.logout().catch(() => {});
    router.replace("/login");
    router.refresh();
  };

  return (
    <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[var(--sidebar-w)] flex-col border-r border-line glass z-30">
      <Link href="/" className="flex items-center gap-2.5 px-5 h-16 shrink-0">
        <Mascot mood="idle" size={34} />
        <span className="font-extrabold text-lg tracking-tight">Mocker</span>
      </Link>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mb-5">
            <p className="px-3 mb-1.5 text-[10px] font-extrabold uppercase tracking-[0.13em] text-muted">{group.title}</p>
            <ul className="flex flex-col gap-0.5">
              {group.links.filter((l) => !l.adminOnly || user?.is_admin).map((l) => {
                const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
                const Icon = l.icon;
                const badge = l.href === "/review" && due?.due_now ? due.due_now : null;
                return (
                  <li key={l.href}>
                    <Link href={l.href} title={l.hint}
                      className={`relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-bold transition
                        ${active ? "text-primary" : "text-ink-soft hover:text-ink hover:bg-surface-2"}`}>
                      {active && (
                        <motion.span layoutId="nav-active" transition={{ type: "spring", stiffness: 420, damping: 34 }}
                          className="absolute inset-0 rounded-xl bg-primary-soft border border-primary-line" />
                      )}
                      <Icon size={17} strokeWidth={2.4} className="relative shrink-0" />
                      <span className="relative truncate">{l.label}</span>
                      {badge ? (
                        <span className="relative ml-auto rounded-full bg-accent text-accent-ink text-[10px] font-extrabold px-1.5 py-0.5 tabular">
                          {badge}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-line p-3">
        <div className="rounded-xl bg-surface-2 p-3">
          <p className="text-xs font-extrabold truncate">{user?.name ?? "…"}</p>
          <div className="flex items-center gap-3 mt-1.5 text-[11px] font-extrabold text-muted">
            <span className="inline-flex items-center gap-1"><Flame size={13} className="text-accent" />{stats?.current_streak ?? 0}</span>
            <span className="inline-flex items-center gap-1"><Sparkles size={13} className="text-primary" />{stats?.total_points ?? 0}</span>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <ThemeToggle compact />
          <span className="text-[11px] font-extrabold text-muted">Theme</span>
        </div>
        <button onClick={startTour}
          className="mt-2 w-full flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-extrabold text-muted hover:text-ink hover:bg-surface-2 transition">
          <Compass size={15} /> Take the tour
        </button>
        <button onClick={logout}
          className="mt-1 w-full flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-extrabold text-muted hover:text-ink hover:bg-surface-2 transition">
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </aside>
  );
}
