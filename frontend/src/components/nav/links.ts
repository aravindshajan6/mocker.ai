import {
  BarChart3, BookMarked, BookOpenCheck, CalendarCheck, FileClock, Home, Newspaper, RotateCcw, Settings,
  ShieldCheck, Timer,
} from "lucide-react";

export type NavLink = {
  href: string;
  label: string;
  icon: typeof Home;
  /** Shown in the compact mobile bar */
  primary?: boolean;
  hint?: string;
  /** Hidden from ordinary accounts */
  adminOnly?: boolean;
};

export const NAV_GROUPS: { title: string; links: NavLink[] }[] = [
  {
    title: "Practise",
    links: [
      { href: "/", label: "Home", icon: Home, primary: true, hint: "Your day at a glance" },
      { href: "/daily", label: "Daily challenge", icon: CalendarCheck, hint: "10 questions, everyone the same set" },
      { href: "/current-affairs", label: "Current affairs", icon: Newspaper, hint: "Generated from today's news" },
      { href: "/practice", label: "Topics", icon: BookOpenCheck, primary: true, hint: "Pick a subject" },
      { href: "/review", label: "Revise", icon: RotateCcw, hint: "Spaced repetition queue" },
    ],
  },
  {
    title: "Test yourself",
    links: [
      { href: "/exam", label: "Exam mode", icon: Timer, primary: true, hint: "Full paper, negative marking" },
      { href: "/history", label: "History", icon: FileClock, hint: "Past attempts" },
    ],
  },
  {
    title: "Look back",
    links: [
      { href: "/answers", label: "My answers", icon: BookMarked, hint: "Every question you've attempted, by subject" },
    ],
  },
  {
    title: "You",
    links: [
      { href: "/progress", label: "Progress", icon: BarChart3, primary: true, hint: "Stats, badges, weak topics" },
      { href: "/settings", label: "Settings", icon: Settings, hint: "Reminders and notifications" },
      { href: "/admin", label: "Admin", icon: ShieldCheck, hint: "Content, keys and accounts", adminOnly: true },
      { href: "/admin/analytics", label: "Analytics", icon: BarChart3, hint: "Usage and learning trends", adminOnly: true },
    ],
  },
];

export const ALL_LINKS: NavLink[] = NAV_GROUPS.flatMap((g) => g.links);
export const PRIMARY_LINKS: NavLink[] = ALL_LINKS.filter((l) => l.primary);

/**
 * Whether a nav link is the current page. The most specific match wins, so /admin/analytics
 * lights "Analytics" and not also "Admin" — two lit items would share one animated highlight.
 */
export function isActiveLink(href: string, pathname: string): boolean {
  const matches = (h: string) => (h === "/" ? pathname === "/" : pathname === h || pathname.startsWith(`${h}/`));
  if (!matches(href)) return false;
  return !ALL_LINKS.some((o) => o.href !== href && o.href.startsWith(href) && matches(o.href));
}

