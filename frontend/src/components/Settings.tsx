"use client";

import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import ThemeToggle from "@/components/ThemeToggle";
import { Settings as SettingsIcon } from "lucide-react";
import { ErrorNote, Item, PageHeader, SkeletonPage, Stagger } from "@/components/ui";
import { api } from "@/lib/api";
import { currentSubscription, isIOS, isStandalone, permissionState, pushSupported, subscribe, unsubscribe } from "@/lib/push";
import type { Prefs } from "@/lib/types";

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = [0, 15, 30, 45];

function label(h: number, m: number) {
  const ampm = h < 12 ? "am" : "pm";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh}:${String(m).padStart(2, "0")} ${ampm}`;
}

export default function Settings() {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pushOn, setPushOn] = useState(false);

  useEffect(() => {
    api.prefs().then(setPrefs).catch((e) => setError(e?.message || "Could not load your settings."));
    currentSubscription().then((s) => setPushOn(Boolean(s))).catch(() => {});
  }, []);

  const save = async (patch: Partial<Prefs>) => {
    setBusy(true);
    setError(null);
    try {
      setPrefs(await api.savePrefs(patch));
      setNote("Saved");
      setTimeout(() => setNote(null), 1500);
    } catch (e) {
      setError((e as Error)?.message || "Could not save that.");
    } finally {
      setBusy(false);
    }
  };

  const enablePush = async () => {
    if (!prefs) return;
    setBusy(true);
    setError(null);
    try {
      const sub = await subscribe(prefs.vapid_public_key);
      setPrefs(await api.pushSubscribe(sub));
      setPushOn(true);
      setNote("Notifications on for this device");
    } catch (e) {
      setError((e as Error)?.message || "Could not turn on notifications.");
    } finally {
      setBusy(false);
    }
  };

  const disablePush = async () => {
    setBusy(true);
    try {
      const sub = await unsubscribe();
      if (sub) setPrefs(await api.pushUnsubscribe(sub));
      setPushOn(false);
    } catch (e) {
      setError((e as Error)?.message || "Could not turn notifications off.");
    } finally {
      setBusy(false);
    }
  };

  if (error && !prefs) return <p className="mt-10 text-center text-danger font-semibold">{error}</p>;
  if (!prefs) return <SkeletonPage />;

  const perm = permissionState();
  const iosNeedsInstall = isIOS() && !isStandalone();

  return (
    <Stagger className="pt-1 pb-6 flex flex-col gap-4">
      <Item>
        <PageHeader title="Settings" icon={<SettingsIcon size={20} />}
          subtitle="One gentle nudge a day, at a time you choose."
          action={<Mascot mood="idle" size={60} />} />
      </Item>

      <ErrorNote message={error} />
      {note && <p className="text-sm font-extrabold text-success">{note}</p>}

      <Item>
        <div className="card p-4">
          <h2 className="font-extrabold">Appearance</h2>
          <p className="text-sm text-muted font-semibold mt-0.5 mb-3">
            Dark works well for late sessions; “match device” follows your phone&apos;s own setting.
          </p>
          <ThemeToggle />
        </div>
      </Item>

      <section className="card p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-extrabold">Daily reminder</h2>
            <p className="text-sm text-muted font-semibold">Only sent if you haven&apos;t practised that day.</p>
          </div>
          <button role="switch" aria-checked={prefs.reminders_enabled} disabled={busy}
            onClick={() => save({ reminders_enabled: !prefs.reminders_enabled })}
            className={`relative h-7 w-12 rounded-full transition ${prefs.reminders_enabled ? "bg-primary" : "bg-line"}`}>
            <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${prefs.reminders_enabled ? "left-6" : "left-1"}`} />
          </button>
        </div>

        {prefs.reminders_enabled && (
          <div className="mt-4">
            <label className="text-xs font-extrabold text-muted uppercase tracking-wide">Remind me at</label>
            <div className="flex gap-2 mt-1.5">
              <select className="field flex-1" value={prefs.reminder_hour} disabled={busy}
                onChange={(e) => save({ reminder_hour: Number(e.target.value) })}>
                {HOURS.map((h) => <option key={h} value={h}>{label(h, prefs.reminder_minute)}</option>)}
              </select>
              <select className="field w-28" value={prefs.reminder_minute} disabled={busy}
                onChange={(e) => save({ reminder_minute: Number(e.target.value) })}>
                {MINUTES.map((m) => <option key={m} value={m}>:{String(m).padStart(2, "0")}</option>)}
              </select>
            </div>
            <p className="text-xs text-muted font-semibold mt-2">
              Your timezone: {prefs.timezone}.{" "}
              <button className="text-primary font-extrabold underline"
                onClick={() => save({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })}>
                Use this device&apos;s timezone
              </button>
            </p>
            <p className="text-xs text-muted font-semibold mt-2 leading-relaxed">
              Deciding <i>when</i> you will study is the part that makes it stick — pick the time you are
              most often free, not the time you wish you were.
            </p>
          </div>
        )}
      </section>

      <section className="card p-4">
        <h2 className="font-extrabold">Notifications on this device</h2>
        {!pushSupported() ? (
          <p className="text-sm text-muted font-semibold mt-1">This browser doesn&apos;t support notifications.</p>
        ) : iosNeedsInstall ? (
          <p className="text-sm text-muted font-semibold mt-1 leading-relaxed">
            On iPhone and iPad, notifications only work once Mocker is added to your Home Screen.
            Tap <b>Share → Add to Home Screen</b>, then come back here.
          </p>
        ) : perm === "denied" ? (
          <p className="text-sm text-muted font-semibold mt-1">
            Notifications are blocked for this site in your browser settings. Allow them there and reload.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted font-semibold mt-1">
              {pushOn ? "This device will receive your daily nudge." : "Turn on to get the nudge on this device."}
              {prefs.push_devices > 0 && ` ${prefs.push_devices} device${prefs.push_devices === 1 ? "" : "s"} connected.`}
            </p>
            <div className="flex gap-2 mt-3">
              {pushOn ? (
                <>
                  <button className="btn btn-ghost flex-1 !min-h-11" onClick={disablePush} disabled={busy}>Turn off</button>
                  <button className="btn btn-ghost flex-1 !min-h-11" disabled={busy}
                    onClick={async () => {
                      try { await api.pushTest(); setNote("Test notification sent"); }
                      catch (e) { setError((e as Error)?.message || "Could not send a test."); }
                    }}>Send a test</button>
                </>
              ) : (
                <button className="btn btn-primary flex-1 !min-h-11" onClick={enablePush} disabled={busy}>
                  Turn on notifications
                </button>
              )}
            </div>
          </>
        )}
      </section>

      {prefs.telegram_available && (
        <section className="card p-4">
          <h2 className="font-extrabold">Telegram</h2>
          {prefs.telegram_linked ? (
            <>
              <p className="text-sm text-muted font-semibold mt-1">Your reminders also go to Telegram.</p>
              <button className="btn btn-ghost w-full mt-3 !min-h-11" disabled={busy}
                onClick={async () => { setPrefs(await api.telegramUnlink()); }}>Unlink Telegram</button>
            </>
          ) : prefs.telegram_link_url ? (
            <>
              <p className="text-sm text-muted font-semibold mt-1">Open the bot and press start to finish linking.</p>
              <a className="btn btn-primary w-full mt-3 !min-h-11" href={prefs.telegram_link_url} target="_blank" rel="noopener noreferrer">
                Open Telegram →
              </a>
            </>
          ) : (
            <>
              <p className="text-sm text-muted font-semibold mt-1">Get the nudge in Telegram instead of the browser.</p>
              <button className="btn btn-ghost w-full mt-3 !min-h-11" disabled={busy}
                onClick={async () => { setPrefs(await api.telegramLink()); }}>Link Telegram</button>
            </>
          )}
        </section>
      )}
    </Stagger>
  );
}
