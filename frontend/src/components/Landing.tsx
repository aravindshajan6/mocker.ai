"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight, BookOpenCheck, BrainCircuit, CalendarCheck, Check, Flame,
  Newspaper, ShieldCheck, Sparkles, Timer, TrendingUp, WifiOff,
} from "lucide-react";
import Mascot from "@/components/Mascot";
import { Num, spotlight } from "@/components/ui";

type PublicStats = {
  questions: number;
  topics: number;
  past_paper_questions: number;
  topic_list: { slug: string; name: string; icon: string; question_count: number }[];
};

/** Shown before the live numbers arrive so the hero never renders empty or shifts layout. */
const FALLBACK: PublicStats = {
  questions: 6300, topics: 12, past_paper_questions: 234,
  topic_list: [
    { slug: "indian-history", name: "Indian History", icon: "🏛️", question_count: 592 },
    { slug: "kerala", name: "Kerala", icon: "🌴", question_count: 146 },
    { slug: "indian-polity", name: "Constitution & Polity", icon: "⚖️", question_count: 622 },
    { slug: "geography", name: "Geography", icon: "🗺️", question_count: 728 },
    { slug: "economy", name: "Economy", icon: "📈", question_count: 764 },
    { slug: "general-science", name: "General Science", icon: "🔬", question_count: 750 },
    { slug: "english", name: "English", icon: "🔤", question_count: 178 },
    { slug: "environment", name: "Environment", icon: "🌿", question_count: 412 },
  ],
};

export default function Landing() {
  const [stats, setStats] = useState<PublicStats>(FALLBACK);

  useEffect(() => {
    let alive = true;
    fetch("/api/public/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d?.questions) setStats(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const marquee = [...stats.topic_list, ...stats.topic_list];

  return (
    <div className="min-h-dvh">
      {/* ---------------------------------------------------------------- nav --- */}
      <header className="sticky top-0 z-40 glass border-b border-line">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <Mascot mood="idle" size={34} />
            <span className="text-lg font-extrabold tracking-tight">Mocker</span>
          </div>
          <nav className="flex items-center gap-1 sm:gap-2">
            <a href="#features" className="hidden rounded-xl px-3 py-2 text-sm font-bold text-ink-soft transition hover:bg-surface-2 hover:text-ink sm:block">Features</a>
            <a href="#how" className="hidden rounded-xl px-3 py-2 text-sm font-bold text-ink-soft transition hover:bg-surface-2 hover:text-ink sm:block">How it works</a>
            <Link href="/login" className="btn btn-primary !min-h-10 !px-5 text-sm">Sign in</Link>
          </nav>
        </div>
      </header>

      {/* --------------------------------------------------------------- hero --- */}
      <section className="aurora relative px-4 pb-16 pt-14 sm:px-6 sm:pb-24 sm:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <div className="pop-in flex justify-center">
            <Mascot mood="wave" size={132} />
          </div>

          <span className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-primary-line bg-primary-soft px-3 py-1.5 text-[11px] font-extrabold uppercase tracking-wider text-primary">
            <Sparkles size={13} /> Built for Kerala PSC · SSC · UPSC
          </span>

          <h1 className="balance mt-4 text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-6xl">
            One more question,<br />
            <span className="text-grad">every single day.</span>
          </h1>

          <p className="pretty mx-auto mt-5 max-w-xl text-base font-semibold leading-relaxed text-ink-soft sm:text-lg">
            A calm, ad-free way to build General Knowledge for competitive exams.
            Ten questions a day, a streak worth protecting, and a small elephant who
            genuinely believes in you.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/login" className="glow-ring btn btn-primary w-full px-8 text-base sm:w-auto">
              Start practising <ArrowRight size={18} />
            </Link>
            <a href="#features" className="btn btn-ghost w-full px-7 text-base sm:w-auto">See what&apos;s inside</a>
          </div>

          <p className="mt-4 text-xs font-bold text-muted">
            Free · No advertisements · Works offline
          </p>

          {/* live counts */}
          <dl className="mx-auto mt-12 grid max-w-2xl grid-cols-3 gap-3">
            {[
              { label: "Questions", value: stats.questions, tone: "text-primary" },
              { label: "Subjects", value: stats.topics, tone: "text-accent" },
              { label: "From real papers", value: stats.past_paper_questions, tone: "text-info" },
            ].map((s) => (
              <div key={s.label} className="card lift-edge p-4">
                <dd className={`text-2xl font-extrabold sm:text-3xl ${s.tone}`}><Num value={s.value} /></dd>
                <dt className="mt-1 text-[10px] font-extrabold uppercase tracking-wider text-muted">{s.label}</dt>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ------------------------------------------------------------ marquee --- */}
      <section className="defer-paint border-y border-line bg-surface/50 py-5" aria-label="Subjects covered">
        <div className="marquee mask-fade-x">
          <div className="marquee-track gap-3" style={{ ["--marquee-duration" as string]: "48s" }}>
            {marquee.map((t, i) => (
              <span
                key={`${t.slug}-${i}`}
                aria-hidden={i >= stats.topic_list.length}
                className="flex shrink-0 items-center gap-2 rounded-2xl border border-line bg-surface px-4 py-2.5 text-sm font-extrabold"
              >
                <span className="text-lg">{t.icon}</span>
                {t.name}
                <span className="text-xs font-bold text-muted">{t.question_count}</span>
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- features --- */}
      <section id="features" className="defer-paint px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-5xl">
          <div className="reveal-up mx-auto max-w-2xl text-center">
            <h2 className="balance text-3xl font-extrabold tracking-tight sm:text-4xl">
              Everything you need, nothing you don&apos;t
            </h2>
            <p className="pretty mt-3 font-semibold text-ink-soft">
              No feed to scroll, no badges for logging in. Just the things that actually
              move a score.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-6">
            {/* daily — wide hero cell */}
            <article className="card card-hero reveal-up p-6 sm:col-span-4 sm:p-8">
              <div className="relative">
                <span className="text-[11px] font-extrabold uppercase tracking-[0.14em] opacity-80">The daily challenge</span>
                <h3 className="mt-2 text-2xl font-extrabold sm:text-3xl">The same ten questions as everyone else</h3>
                <p className="pretty mt-3 max-w-md font-semibold leading-relaxed opacity-90">
                  A fresh set every morning, identical for every learner, so scores are
                  genuinely comparable. Three slots are quietly swapped for questions
                  you&apos;re about to forget.
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  {["+25 finishing bonus", "Streak keeper", "Resume any time"].map((t) => (
                    <span key={t} className="rounded-full bg-white/20 px-3 py-1.5 text-xs font-extrabold">{t}</span>
                  ))}
                </div>
              </div>
            </article>

            {/* streak */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-2"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><Flame size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Streaks that forgive</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Miss a day and we&apos;ll repair it for you, twice a month. Life happens;
                  your run shouldn&apos;t end because of it.
                </p>
              </div>
            </article>

            {/* revision */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-3"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-soft text-primary"><BrainCircuit size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Revision, timed by science</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Every answer feeds a spaced-repetition schedule. Questions come back
                  just before you&apos;d forget them — not a week too late.
                </p>
              </div>
            </article>

            {/* exam */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-3"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-info-soft text-info"><Timer size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Exam mode, properly scored</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Full-length timed papers with ⅓ negative marking, a question palette
                  and a server-held clock. Afterwards it tells you when guessing paid.
                </p>
              </div>
            </article>

            {/* current affairs */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-2"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><Newspaper size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Current affairs, daily</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Fresh questions written each morning from the day&apos;s news, with the
                  source article one tap away.
                </p>
              </div>
            </article>

            {/* offline */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-2"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-soft text-primary"><WifiOff size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Works without signal</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Install it like an app. Answers you give on a train sync themselves
                  the moment you&apos;re back online.
                </p>
              </div>
            </article>

            {/* progress */}
            <article
              onPointerMove={spotlight}
              className="card card-interactive spotlight reveal-up flex flex-col justify-between p-6 sm:col-span-2"
            >
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-info-soft text-info"><TrendingUp size={20} /></div>
              <div className="mt-4">
                <h3 className="text-lg font-extrabold">Knows your weak spots</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">
                  Practice sets weight themselves towards the subjects you keep getting
                  wrong, and tell you whether you&apos;re improving.
                </p>
              </div>
            </article>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- how --- */}
      <section id="how" className="defer-paint border-y border-line bg-surface/40 px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-4xl">
          <div className="reveal-up text-center">
            <h2 className="balance text-3xl font-extrabold tracking-tight sm:text-4xl">Ten minutes a day is the whole method</h2>
            <p className="pretty mx-auto mt-3 max-w-xl font-semibold text-ink-soft">
              Consistency beats cramming. The app is designed around one short, finishable session.
            </p>
          </div>

          <ol className="mt-12 grid gap-4 sm:grid-cols-3">
            {[
              { n: "01", icon: CalendarCheck, title: "Do today's ten", body: "One set, all subjects, finishable on a tea break. Finish it and your streak survives another day." },
              { n: "02", icon: BookOpenCheck, title: "Practise the weak ones", body: "Pick a subject, or let the app choose the three you keep dropping marks in." },
              { n: "03", icon: Timer, title: "Sit a full paper", body: "When the exam is close, run a timed mock with real negative marking and see where you stand." },
            ].map((s) => (
              <li key={s.n} className="card reveal-up lift-edge p-6">
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-soft text-primary"><s.icon size={20} /></div>
                  <span className="text-2xl font-extrabold text-line-strong">{s.n}</span>
                </div>
                <h3 className="mt-4 text-lg font-extrabold">{s.title}</h3>
                <p className="pretty mt-1.5 text-sm font-semibold text-ink-soft">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* -------------------------------------------------------------- trust --- */}
      <section className="defer-paint px-4 py-20 sm:px-6">
        <div className="mx-auto grid max-w-5xl items-center gap-10 sm:grid-cols-2">
          <div className="reveal-up">
            <h2 className="balance text-3xl font-extrabold tracking-tight sm:text-4xl">
              Questions you can actually trust
            </h2>
            <p className="pretty mt-4 font-semibold leading-relaxed text-ink-soft">
              A quiz app is only as good as its answer key. Ours is built from
              hand-authored banks and <strong className="text-ink">{stats.past_paper_questions} questions
              lifted from official Kerala PSC papers</strong>, then audited on a schedule —
              anything doubtful is retired rather than quietly served to you.
            </p>
            <ul className="mt-6 flex flex-col gap-3">
              {[
                "Reproduced verbatim from official answer keys",
                "Explanations on every single question",
                "Nightly automated answer-key audit",
                "No advertisements, no tracking, no upsell",
              ].map((t) => (
                <li key={t} className="flex items-start gap-2.5 text-sm font-bold">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-success-soft text-success">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>

          <div className="reveal-up card card-2 p-6">
            <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-muted">
              <ShieldCheck size={15} className="text-primary" /> Sample question
            </div>
            <p className="mt-3 text-lg font-extrabold leading-snug">
              Vasco da Gama first set foot on Indian soil in 1498 at Kappad, which lies in
              which present-day district?
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {[
                { t: "Kannur", s: "" },
                { t: "Kozhikode", s: "correct" },
                { t: "Malappuram", s: "" },
                { t: "Thrissur", s: "" },
              ].map((o, i) => (
                <div
                  key={o.t}
                  data-state={o.s || undefined}
                  className="option !cursor-default"
                >
                  <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs font-extrabold ${o.s ? "bg-success text-white" : "bg-surface-2 text-muted"}`}>
                    {o.s ? <Check size={15} strokeWidth={3} /> : ["A", "B", "C", "D"][i]}
                  </span>
                  <span className="pt-0.5 font-semibold leading-snug">{o.t}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-2xl bg-success-soft p-4">
              <p className="font-extrabold text-success">You got it!</p>
              <p className="mt-1 text-sm font-semibold leading-relaxed">
                Kappad, near Koyilandy in Kozhikode district, is where Vasco da Gama landed on
                20 May 1498, opening the direct sea route from Europe to India.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- final CTA --- */}
      <section className="defer-paint px-4 pb-20 sm:px-6">
        <div className="card-hero reveal-up mx-auto max-w-3xl px-6 py-14 text-center sm:px-12">
          <div className="relative flex flex-col items-center">
            <Mascot mood="celebrate" size={104} />
            <h2 className="balance mt-4 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Your streak starts today
            </h2>
            <p className="pretty mt-3 max-w-md font-semibold opacity-90">
              Ten questions. Ten minutes. Kunju is already waiting.
            </p>
            <Link
              href="/login"
              className="btn mt-8 w-full bg-white/95 px-8 text-base text-[#12463c] hover:bg-white sm:w-auto"
            >
              Sign in and begin <ArrowRight size={18} />
            </Link>
            <p className="mt-4 text-xs font-bold opacity-80">
              Accounts are provisioned by an administrator.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- footer --- */}
      <footer className="border-t border-line px-4 py-10 sm:px-6">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Mascot mood="idle" size={30} />
            <span className="font-extrabold tracking-tight">Mocker</span>
          </div>
          <p className="max-w-xl text-[11px] font-semibold leading-relaxed text-muted">
            Previous-year questions are reproduced from official papers published by the{" "}
            <a href="https://www.keralapsc.gov.in" target="_blank" rel="noopener noreferrer" className="underline">
              Kerala Public Service Commission
            </a>. Mocker is an independent study tool and is not affiliated with or endorsed by the KPSC.
          </p>
        </div>
      </footer>
    </div>
  );
}
