"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Mascot from "@/components/Mascot";
import { ErrorNote } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
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
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center text-center mb-6">
          <Mascot mood="wave" size={120} />
          <h1 className="text-2xl font-extrabold mt-2">{isLogin ? "Welcome back!" : "Hi, I'm Kunju."}</h1>
          <p className="text-muted font-semibold mt-1">
            {isLogin ? "Ready for a few questions?" : "Let's make studying a daily habit — one question at a time."}
          </p>
        </div>
        <form onSubmit={submit} className="card p-5 flex flex-col gap-3">
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
            <>New here? <Link className="text-primary font-extrabold" href="/register">Create an account</Link></>
          ) : (
            <>Already have an account? <Link className="text-primary font-extrabold" href="/login">Sign in</Link></>
          )}
        </p>
      </div>
    </div>
  );
}
