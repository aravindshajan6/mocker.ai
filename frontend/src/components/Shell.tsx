"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

const tabs = [
  { href: "/", label: "Home", icon: "🏠" },
  { href: "/progress", label: "Progress", icon: "📈" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const inQuiz = pathname.startsWith("/quiz/");

  const logout = async () => {
    await api.logout();
    router.replace("/login");
    router.refresh();
  };

  return (
    <div className="flex flex-col min-h-dvh">
      {!inQuiz && (
        <header className="sticky top-0 z-20 backdrop-blur bg-bg/80 border-b border-line">
          <div className="mx-auto max-w-2xl px-4 h-14 flex items-center justify-between">
            <Link href="/" className="font-extrabold text-lg tracking-tight text-primary">Mocker</Link>
            <nav className="hidden sm:flex items-center gap-1">
              {tabs.map((t) => (
                <Link key={t.href} href={t.href}
                  className={`px-3 py-1.5 rounded-xl text-sm font-bold transition ${pathname === t.href ? "bg-primary-soft text-primary" : "text-muted hover:text-ink"}`}>
                  {t.label}
                </Link>
              ))}
              <button onClick={logout} className="px-3 py-1.5 rounded-xl text-sm font-bold text-muted hover:text-ink">Sign out</button>
            </nav>
            <button onClick={logout} className="sm:hidden text-sm font-bold text-muted">Sign out</button>
          </div>
        </header>
      )}
      <main className="flex-1 mx-auto w-full max-w-2xl px-4 pb-24 sm:pb-10">{children}</main>
      {!inQuiz && (
        <footer className="mx-auto w-full max-w-2xl px-4 pb-24 sm:pb-6 text-[11px] leading-relaxed text-muted font-semibold">
          Previous-year questions are reproduced from official papers published by the{" "}
          <a href="https://www.keralapsc.gov.in" target="_blank" rel="noopener noreferrer" className="underline">Kerala Public Service Commission</a>.
          Mocker is an independent study tool and is not affiliated with or endorsed by the KPSC.
        </footer>
      )}
      {!inQuiz && (
        <nav className="sm:hidden fixed bottom-0 inset-x-0 z-20 border-t border-line bg-surface/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
          <div className="grid grid-cols-2 max-w-2xl mx-auto">
            {tabs.map((t) => (
              <Link key={t.href} href={t.href}
                className={`flex flex-col items-center gap-0.5 py-2.5 text-xs font-bold ${pathname === t.href ? "text-primary" : "text-muted"}`}>
                <span className="text-xl leading-none">{t.icon}</span>
                {t.label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </div>
  );
}
