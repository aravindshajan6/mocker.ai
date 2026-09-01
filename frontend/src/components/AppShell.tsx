"use client";

import { usePathname } from "next/navigation";
import { MotionConfig } from "motion/react";
import { AppDataProvider } from "@/components/AppData";
import Sidebar from "@/components/nav/Sidebar";
import MobileNav from "@/components/nav/MobileNav";
import PageTransition from "@/components/PageTransition";

/** Chrome is hidden entirely while a quiz or exam is running — that is the whole point of the app. */
function isFocusMode(pathname: string) {
  return /^\/quiz\/[^/]+$/.test(pathname) || /^\/exam\/[^/]+$/.test(pathname);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const focus = isFocusMode(pathname);

  return (
    // reducedMotion="user" drops transform and layout animations for people who ask for less
    // motion, while keeping opacity and colour — so the app still feels responsive, not frozen.
    <MotionConfig reducedMotion="user">
    <AppDataProvider>
      {focus ? (
        <main className="mx-auto w-full max-w-2xl px-4">{children}</main>
      ) : (
        <div className="min-h-dvh">
          <Sidebar />
          <MobileNav />
          <div className="lg:pl-[var(--sidebar-w)]">
            <main className="mx-auto w-full max-w-3xl px-4 pb-24 lg:pb-12 lg:pt-6">
              <PageTransition>{children}</PageTransition>
            </main>
            <footer className="mx-auto w-full max-w-3xl px-4 pb-24 lg:pb-8 text-[11px] leading-relaxed text-muted font-semibold">
              Previous-year questions are reproduced from official papers published by the{" "}
              <a href="https://www.keralapsc.gov.in" target="_blank" rel="noopener noreferrer" className="underline">Kerala Public Service Commission</a>.
              Mocker is an independent study tool and is not affiliated with or endorsed by the KPSC.
            </footer>
          </div>
        </div>
      )}
    </AppDataProvider>
    </MotionConfig>
  );
}
