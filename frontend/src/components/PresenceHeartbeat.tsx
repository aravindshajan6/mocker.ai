"use client";

import { useEffect } from "react";

const PING_MS = 30_000;
/** No input for this long counts as away, even if the tab is still on screen. */
const IDLE_MS = 120_000;

/**
 * Tells the server the app is being used, so the admin panel can report screen time. A ping is
 * sent only while the tab is visible AND the person has touched, typed or scrolled recently —
 * a tab left open on a desk earns nothing. The request carries no body: nothing about what is
 * on screen leaves the device. The server caps each ping's credit at the real time since the
 * previous one, so extra tabs or retries cannot inflate the total.
 */
export default function PresenceHeartbeat() {
  useEffect(() => {
    let lastInput = Date.now();
    const onInput = () => { lastInput = Date.now(); };
    const onVisible = () => { if (document.visibilityState === "visible") lastInput = Date.now(); };
    const events = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;
    events.forEach((e) => window.addEventListener(e, onInput, { passive: true, capture: true }));
    document.addEventListener("visibilitychange", onVisible);

    const timer = setInterval(() => {
      if (document.visibilityState !== "visible" || !navigator.onLine) return;
      if (Date.now() - lastInput > IDLE_MS) return;
      // Plain fetch, not the api client: a failed heartbeat must never trigger its sign-out
      // redirect or offline queue. Losing one ping costs at most one interval of screen time.
      fetch("/api/me/heartbeat", { method: "POST", credentials: "same-origin", keepalive: true }).catch(() => {});
    }, PING_MS);

    return () => {
      clearInterval(timer);
      events.forEach((e) => window.removeEventListener(e, onInput, { capture: true }));
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return null;
}
