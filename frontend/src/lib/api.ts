import type {
  ActiveSession, AnswerResult, CurrentAffairs, Daily, FinishResult, HistoryRow, LeaderboardRow, QuizSession, Stats, Topic,
  User,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
      // Cookie present but invalid/expired: full reload so the proxy redirects cleanly.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      location.href = "/login";
    }
    throw new ApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const get = <T,>(path: string) => request<T>(path);

export const api = {
  register: (data: { name: string; email: string; password: string }) => post<User>("/api/auth/register", data),
  login: (data: { email: string; password: string }) => post<User>("/api/auth/login", data),
  logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  me: () => get<User>("/api/auth/me"),
  topics: () => get<Topic[]>("/api/topics"),
  daily: () => get<Daily>("/api/quiz/daily"),
  active: () => get<ActiveSession[]>("/api/quiz/active"),
  startQuiz: (data: { mode: "daily" | "topic" | "mixed" | "current-affairs"; topic?: string; count?: number; day?: string }) => post<QuizSession>("/api/quiz/start", data),
  currentAffairs: () => get<CurrentAffairs>("/api/current-affairs"),
  session: (id: string) => get<QuizSession>(`/api/quiz/${id}`),
  answer: (id: string, question_id: number, selected_index: number) => post<AnswerResult>(`/api/quiz/${id}/answer`, { question_id, selected_index }),
  finish: (id: string) => post<FinishResult>(`/api/quiz/${id}/finish`),
  abandon: (id: string) => post<{ ok: boolean }>(`/api/quiz/${id}/abandon`),
  stats: () => get<Stats>("/api/me/stats"),
  history: () => get<HistoryRow[]>("/api/me/history"),
  leaderboard: () => get<LeaderboardRow[]>("/api/me/leaderboard"),
};

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Burning the midnight oil";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 21) return "Good evening";
  return "Winding down";
}
