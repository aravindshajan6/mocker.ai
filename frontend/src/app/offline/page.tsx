import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Offline" };

/** Shown by the service worker when a page is requested with no connection. */
export default function OfflinePage() {
  return (
    <div className="min-h-dvh flex flex-col items-center justify-center text-center px-6 gap-3">
      <span className="text-5xl">📴</span>
      <h1 className="text-2xl font-extrabold">You&apos;re offline</h1>
      <p className="text-muted font-semibold max-w-xs">
        Mocker needs a connection to load new questions. Anything you answered while offline is saved
        and will sync as soon as you&apos;re back.
      </p>
      <Link href="/" className="btn btn-primary mt-2">Try again</Link>
    </div>
  );
}
