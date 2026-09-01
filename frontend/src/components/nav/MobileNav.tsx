"use client";

import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Compass, Flame, LogOut, Menu, Sparkles, X } from "lucide-react";
import Mascot from "@/components/Mascot";
import { startTour } from "@/components/Tour";
import ThemeToggle from "@/components/ThemeToggle";
import { useAppData } from "@/components/AppData";
import { NAV_GROUPS, PRIMARY_LINKS } from "./links";
import { api } from "@/lib/api";

export default function MobileNav() {
  const { scrollY } = useScroll();
  const [hidden, setHidden] = useState(false);
  useMotionValueEvent(scrollY, "change", (y) => {
    setHidden(y > (scrollY.getPrevious() ?? 0) && y > 80);
  });
  const pathname = usePathname();
  const router = useRouter();
  const { stats, due, user } = useAppData();
  const [open, setOpen] = useState(false);


  const logout = async () => {
    await api.logout().catch(() => {});
    router.replace("/login");
    router.refresh();
  };

  return (
    <>
      {/* The header slides away while scrolling down and returns on the first upward scroll,
          reclaiming 56px of a small screen. Motion values bypass React rendering; setState only
          fires when the direction flips, not per frame. */}
      <motion.header className="lg:hidden sticky top-0 z-30 glass border-b border-line"
        animate={{ y: hidden ? "-100%" : 0 }} transition={{ duration: 0.2, ease: "easeOut" }}>
        <div className="mx-auto max-w-2xl h-14 px-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Mascot mood="idle" size={28} />
            <span className="font-extrabold tracking-tight">Mocker</span>
          </Link>
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2.5 py-1 text-[11px] font-extrabold text-accent-ink">
              <Flame size={12} /> {stats?.current_streak ?? 0}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-extrabold text-primary">
              <Sparkles size={12} /> {stats?.total_points ?? 0}
            </span>
            <ThemeToggle compact />
            <button onClick={() => setOpen(true)} aria-label="Open menu"
              className="h-9 w-9 grid place-items-center rounded-xl bg-surface-2 text-ink">
              <Menu size={18} />
            </button>
          </div>
        </div>
      </motion.header>

      <AnimatePresence>
        {open && (
          <>
            <motion.div key="scrim" className="lg:hidden fixed inset-0 z-40 bg-black/45"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setOpen(false)} />
            <motion.aside key="drawer"
              className="lg:hidden fixed inset-y-0 right-0 z-50 w-[85%] max-w-xs bg-surface border-l border-line flex flex-col"
              initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 380, damping: 38 }}>
              <div className="h-14 px-4 flex items-center justify-between border-b border-line">
                <span className="font-extrabold">Menu</span>
                <button onClick={() => setOpen(false)} aria-label="Close menu"
                  className="h-9 w-9 grid place-items-center rounded-xl bg-surface-2"><X size={18} /></button>
              </div>
              <nav className="flex-1 overflow-y-auto p-3">
                {NAV_GROUPS.map((g) => (
                  <div key={g.title} className="mb-4">
                    <p className="px-2 mb-1 text-[10px] font-extrabold uppercase tracking-[0.13em] text-muted">{g.title}</p>
                    {g.links.filter((l) => !l.adminOnly || user?.is_admin).map((l) => {
                      const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
                      const Icon = l.icon;
                      const badge = l.href === "/review" && due?.due_now ? due.due_now : null;
                      return (
                        <Link key={l.href} href={l.href} onClick={() => setOpen(false)}
                          className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-bold transition
                            ${active ? "bg-primary-soft text-primary" : "text-ink-soft hover:bg-surface-2"}`}>
                          <Icon size={17} strokeWidth={2.4} />
                          {l.label}
                          {badge ? <span className="ml-auto rounded-full bg-accent text-accent-ink text-[10px] font-extrabold px-1.5 py-0.5">{badge}</span> : null}
                        </Link>
                      );
                    })}
                  </div>
                ))}
              </nav>
              <div className="border-t border-line p-3">
                <p className="text-xs font-extrabold truncate px-1">{user?.name}</p>
                <button onClick={() => { setOpen(false); startTour(); }}
                  className="mt-2 w-full flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-extrabold text-muted hover:bg-surface-2">
                  <Compass size={16} /> Take the tour
                </button>
                <button onClick={logout} className="mt-1 w-full flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-extrabold text-muted hover:bg-surface-2">
                  <LogOut size={16} /> Sign out
                </button>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 glass border-t border-line pb-[env(safe-area-inset-bottom)]">
        <div className="grid grid-cols-4 max-w-2xl mx-auto">
          {PRIMARY_LINKS.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            const Icon = l.icon;
            return (
              <Link key={l.href} href={l.href}
                className={`relative flex flex-col items-center gap-0.5 py-2 text-[10px] font-extrabold transition ${active ? "text-primary" : "text-muted"}`}>
                {active && (
                  <motion.span layoutId="mobile-nav-active" transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    className="absolute -top-px h-0.5 w-8 rounded-full bg-primary" />
                )}
                <Icon size={19} strokeWidth={2.4} />
                {l.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
