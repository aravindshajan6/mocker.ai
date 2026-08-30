"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Mascot from "@/components/Mascot";
import { ErrorNote } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const [signupOpen, setSignupOpen] = useState(false);
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The sign-up route stays reachable for an operator who re-opens registration, but the link is
    // hidden while it is closed so nobody is invited into a dead end.
    const t = setTimeout(() => void api.authConfig().then((c) => setSignupOpen(c.allow_signup)).catch(() => {}), 0);
    return () => clearTimeout(t);
  }, []);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isLogin) await api.login({ email, password });
      else await api.register({ name, email, password });
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-dvh flex items-center justify-center px-4 py-10">
      <motion.div className="w-full max-w-sm"
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}>
        <div className="flex flex-col items-center text-center mb-6">
          <Mascot mood="wave" size={120} />
          <h1 className="text-2xl font-extrabold mt-2">{isLogin ? "Welcome back!" : "Hi, I'm Kunju."}</h1>
          <p className="text-muted font-semibold mt-1">
            {isLogin ? "Ready for a few questions?" : "Let's make studying a daily habit — one question at a time."}
          </p>
        </div>
        <form onSubmit={submit} className="card card-2 p-5 flex flex-col gap-3">
          {!isLogin && (
            <label className="flex flex-col gap-1 text-sm font-bold">
              Your name
              <input className="field" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoComplete="name" placeholder="e.g. Anjali" />
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm font-bold">
            Email
            <input className="field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@example.com" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-bold">
            Password
            <input className="field" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete={isLogin ? "current-password" : "new-password"} placeholder={isLogin ? "Your password" : "At least 6 characters"} />
          </label>
          <ErrorNote message={error} />
          <button className="btn btn-primary mt-1" disabled={busy}>
            {busy ? "One moment…" : isLogin ? "Sign in" : "Create my account"}
          </button>
        </form>
        <p className="text-center text-sm font-semibold text-muted mt-5">
          {isLogin ? (
            signupOpen
              ? <>New here? <Link className="text-primary font-extrabold" href="/register">Create an account</Link></>
              : <>Accounts are set up by an administrator. Ask for one if you don&apos;t have it yet.</>
          ) : (
            <>Already have an account? <Link className="text-primary font-extrabold" href="/login">Sign in</Link></>
          )}
        </p>
        <ul className="mt-6 grid grid-cols-3 gap-2 text-center">
          {[["6,000+", "questions"], ["Daily", "current affairs"], ["Zero", "ads"]].map(([a, b]) => (
            <li key={b} className="rounded-2xl bg-surface-2 px-2 py-2.5">
              <div className="text-sm font-extrabold">{a}</div>
              <div className="text-[10px] font-extrabold text-muted uppercase tracking-wide">{b}</div>
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  );
}
