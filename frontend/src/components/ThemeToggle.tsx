"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

export type Theme = "light" | "dark" | "system";
const KEY = "mocker:theme";
const ORDER: Theme[] = ["system", "light", "dark"];

/**
 * Reads the stored preference and applies it. `system` removes the attribute entirely so the CSS
 * falls back to prefers-color-scheme, which is why the palette defines both.
 */
export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

const META = {
  system: { icon: Monitor, label: "Match device" },
  light: { icon: Sun, label: "Light" },
  dark: { icon: Moon, label: "Dark" },
} as const;

/** Segmented control — three explicit choices read better than a two-state switch with a hidden third. */
export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const id = setTimeout(() => setTheme(readTheme()), 0);
    return () => clearTimeout(id);
  }, []);

  const choose = (t: Theme) => {
    setTheme(t);
    applyTheme(t);
    try { localStorage.setItem(KEY, t); } catch { /* private mode */ }
  };

  if (compact) {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
    const Icon = META[theme].icon;
    return (
      <button onClick={() => choose(next)} title={`Theme: ${META[theme].label} — switch to ${META[next].label}`}
        aria-label={`Theme: ${META[theme].label}. Switch to ${META[next].label}`}
        className="h-9 w-9 grid place-items-center rounded-xl bg-surface-2 text-ink-soft hover:text-ink transition">
        <Icon size={16} />
      </button>
    );
  }

  return (
    <div className="inline-flex gap-1 rounded-2xl bg-surface-2 p-1" role="radiogroup" aria-label="Colour theme">
      {ORDER.map((t) => {
        const Icon = META[t].icon;
        const active = theme === t;
        return (
          <button key={t} role="radio" aria-checked={active} onClick={() => choose(t)}
            className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-extrabold transition
              ${active ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"}`}>
            <Icon size={14} /> {META[t].label}
          </button>
        );
      })}
    </div>
  );
}
