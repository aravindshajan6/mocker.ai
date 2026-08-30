import {
  BarChart3, BookMarked, BookOpenCheck, CalendarCheck, FileClock, Home, Newspaper, RotateCcw, Settings,
  Timer,
} from "lucide-react";

export type NavLink = {
  href: string;
  label: string;
  icon: typeof Home;
  /** Shown in the compact mobile bar */
  primary?: boolean;
  hint?: string;
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
    ],
  },
];

export const ALL_LINKS: NavLink[] = NAV_GROUPS.flatMap((g) => g.links);
export const PRIMARY_LINKS: NavLink[] = ALL_LINKS.filter((l) => l.primary);
