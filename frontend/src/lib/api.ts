import type {
  ActiveSession, AnswerResult, CurrentAffairs, Daily, ExamResult, ExamState, FinishResult, HistoryRow, LeaderboardRow,
  QuizSession, ReviewDue, Stats, Topic, User,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let signingOut = false;

/**
 * The session is gone (expired token, or an account removed server-side). The cookie is httpOnly, so
 * only the server can clear it — do that before navigating, otherwise the proxy still sees a cookie
 * and bounces us straight back, looping forever.
 */
async function handleSignedOut(): Promise<void> {
  if (typeof window === "undefined" || signingOut) return;
  if (location.pathname.startsWith("/login") || location.pathname.startsWith("/register")) return;
  signingOut = true;
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  } catch {
    /* offline or backend down — navigate anyway, the proxy will clear the cookie */
  }
  location.replace("/login");
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
    if (res.status === 401) void handleSignedOut();
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
  startQuiz: (data: { mode: "daily" | "topic" | "mixed" | "current-affairs" | "review"; topic?: string; count?: number; day?: string }) => post<QuizSession>("/api/quiz/start", data),
  reviewQueue: () => get<ReviewDue>("/api/me/review"),
  explain: (questionId: number) => post<{ question_id: number; explanation: string; cached: boolean }>(`/api/quiz/question/${questionId}/explain`),
  currentAffairs: () => get<CurrentAffairs>("/api/current-affairs"),
  session: (id: string) => get<QuizSession>(`/api/quiz/${id}`),
  answer: (id: string, question_id: number, selected_index: number, elapsed_ms?: number) =>
    post<AnswerResult>(`/api/quiz/${id}/answer`, { question_id, selected_index, elapsed_ms }),
  finish: (id: string) => post<FinishResult>(`/api/quiz/${id}/finish`),
  abandon: (id: string) => post<{ ok: boolean }>(`/api/quiz/${id}/abandon`),
  startExam: (data: { count?: number; duration_minutes?: number; topic?: string }) => post<ExamState>("/api/exam/start", data),
  currentExam: () => get<ExamState | null>("/api/exam/current"),
  exam: (id: string) => get<ExamState>(`/api/exam/${id}`),
  saveExamAnswer: (id: string, question_id: number, selected_index: number, marked_for_review: boolean) =>
    post<{ ok: boolean; answered: number; seconds_remaining: number }>(`/api/exam/${id}/answer`, { question_id, selected_index, marked_for_review }),
  submitExam: (id: string) => post<ExamResult>(`/api/exam/${id}/submit`),
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
