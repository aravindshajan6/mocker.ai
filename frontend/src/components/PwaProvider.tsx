"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/** navigator.onLine is external browser state, so it is read through a store rather than an effect. */
function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/**
 * Registers the service worker, replays anything answered offline, and offers an install prompt.
 *
 * Installing matters beyond convenience: on iOS, a site can only receive push notifications once it
 * has been added to the Home Screen, so this is the gate on reminders working there at all.
 */
export default function PwaProvider() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [dismissed, setDismissed] = useState(true);   // never offered before the third visit
  const offline = useSyncExternalStore(subscribeOnline, () => !navigator.onLine, () => false);
  const [synced, setSynced] = useState<number | null>(null);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const register = () => navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
    register();

    const flush = () => navigator.serviceWorker.controller?.postMessage("flush-outbox");
    const onOnline = () => flush();
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "outbox-flushed" && e.data.count) {
        setSynced(e.data.count);
        setTimeout(() => setSynced(null), 4000);
      }
    };
    window.addEventListener("online", onOnline);
    navigator.serviceWorker.addEventListener("message", onMessage);
    flush();
    return () => {
      window.removeEventListener("online", onOnline);
      navigator.serviceWorker.removeEventListener("message", onMessage);
    };
  }, []);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setPrompt(e as InstallPrompt);
      // Never interrupt on a first visit — only offer once someone has actually used the app.
      try {
        const visits = Number(localStorage.getItem("mocker:visits") || "0") + 1;
        localStorage.setItem("mocker:visits", String(visits));
        setDismissed(localStorage.getItem("mocker:install-dismissed") === "1" || visits < 3);
      } catch {
        setDismissed(false);
      }
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const install = async () => {
    if (!prompt) return;
    await prompt.prompt();
    await prompt.userChoice;
    setPrompt(null);
  };

  const dismiss = () => {
    setDismissed(true);
    try { localStorage.setItem("mocker:install-dismissed", "1"); } catch { /* private mode */ }
  };

  return (
    <>
      {offline && (
        <div className="fixed top-0 inset-x-0 z-50 bg-accent text-ink text-center text-xs font-extrabold py-1.5">
          Offline — your answers are being saved and will sync automatically
        </div>
      )}
      {synced !== null && (
        <div className="fixed top-0 inset-x-0 z-50 bg-success text-white text-center text-xs font-extrabold py-1.5 pop-in">
          Synced {synced} answer{synced === 1 ? "" : "s"} you gave offline
        </div>
      )}
      {prompt && !dismissed && (
        <div className="fixed bottom-20 sm:bottom-4 inset-x-3 z-40 card p-3 flex items-center gap-3 pop-in">
          <span className="text-2xl">📲</span>
          <div className="flex-1 min-w-0">
            <p className="font-extrabold text-sm">Add Mocker to your home screen</p>
            <p className="text-xs text-muted font-semibold">Opens instantly, works offline, and can remind you.</p>
          </div>
          <button className="text-xs font-extrabold text-primary px-2" onClick={install}>Add</button>
          <button className="text-xs font-extrabold text-muted px-1" onClick={dismiss} aria-label="Dismiss">✕</button>
        </div>
      )}
    </>
  );
}
