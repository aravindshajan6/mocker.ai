import type {
  ActiveSession, AnswerResult, CurrentAffairs, Daily, ExamResult, ExamState, FinishResult, HistoryRow, LeaderboardRow,
  AdminOverview, AdminQuestion, AdminUserRow, Answers, Credential, Insights, Prefs, QuizSession, ReviewDue,
  Stats, Topic, User,
} from "./types";

/** Thrown when the service worker accepted a write for later replay instead of sending it. */
export class QueuedOffline extends Error {
  constructor() {
    super("Saved offline — this will sync when you're back online.");
    this.name = "QueuedOffline";
  }
}

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
  let res: Response;
  try {
    res = await doFetch(path, init);
  } catch {
    // A dropped connection surfaces as a bare TypeError; say something a person can act on.
    throw new ApiError(0, navigator.onLine
      ? "Couldn't reach Mocker. Check your connection and try again."
      : "You're offline. Anything you answer is saved and will sync when you're back.");
  }
  return handle<T>(res);
}

let currentUserId: string | null = null;

/** Lets the service worker scope its offline queue to the account that created each entry. */
export function setCurrentUserId(id: string | null) {
  currentUserId = id;
}

export function getCurrentUserId(): string | null {
  return currentUserId;
}

function doFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(currentUserId ? { "X-Mocker-User": currentUserId } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 202) {
    // Queued by the service worker while offline. Signalled as a distinct error rather than a fake
    // result: callers must not render "queued" as if it were a graded answer.
    throw new QueuedOffline();
  }
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
  authConfig: () => get<{ allow_signup: boolean }>("/api/auth/config"),

  // --- admin ---------------------------------------------------------------
  adminOverview: () => get<AdminOverview>("/api/admin/overview"),
  adminUsers: () => get<AdminUserRow[]>("/api/admin/users"),
  adminCreateUser: (d: { name: string; email: string; password: string; is_admin: boolean }) =>
    post<AdminUserRow>("/api/admin/users", d),
  adminResetPassword: (id: string, password: string) => post<{ ok: boolean }>(`/api/admin/users/${id}/password`, { password }),
  adminDeleteUser: (id: string) => request<{ ok: boolean }>(`/api/admin/users/${id}`, { method: "DELETE" }),
  adminKeys: () => get<Credential[]>("/api/admin/llm/keys"),
  adminProviders: () => get<{ providers: { id: string; base_url: string; default_model: string; free_tier: boolean }[]; env_provider: string; env_key_present: boolean }>("/api/admin/llm/providers"),
  adminAddKey: (d: { label: string; provider: string; api_key: string; model?: string; priority?: number }) =>
    post<Credential>("/api/admin/llm/keys", d),
  adminPatchKey: (id: number, d: Record<string, unknown>) =>
    request<Credential>(`/api/admin/llm/keys/${id}`, { method: "PATCH", body: JSON.stringify(d) }),
  adminDeleteKey: (id: number) => request<{ ok: boolean }>(`/api/admin/llm/keys/${id}`, { method: "DELETE" }),
  adminTestKey: (id: number) => post<{ ok: boolean; detail: string; model: string; latency_ms: number | null }>(`/api/admin/llm/keys/${id}/test`),
  adminQuestions: (o: { q?: string; topic?: string; source?: string; only?: string; limit?: number; offset?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(o).forEach(([k, v]) => { if (v !== undefined && v !== "") p.set(k, String(v)); });
    return get<{ questions: AdminQuestion[]; total: number; offset: number; limit: number }>(`/api/admin/questions?${p}`);
  },
  adminAddQuestion: (d: { topic: string; question: string; options: string[]; answer: number; explanation: string; difficulty: number; tags: string[] }) =>
    post<AdminQuestion>("/api/admin/questions", d),
  adminToggleQuestion: (id: number) => post<AdminQuestion>(`/api/admin/questions/${id}/toggle`),
  adminRunNews: (force: boolean) => post<{ started: boolean; detail: string; result: Record<string, unknown> | null }>(`/api/admin/content/current-affairs/run?force=${force}`),
  adminRunAudit: (limit: number) => post<{ started: boolean; detail: string; result: Record<string, unknown> | null }>(`/api/admin/content/audit/run?limit=${limit}`),

  logout: async () => {
    const out = await post<{ ok: boolean }>("/api/auth/logout");
    setCurrentUserId(null);
    // Drop cached API responses and any queued answers so the next person to sign in on this
    // device never sees the previous account's data.
    try {
      (await navigator.serviceWorker?.getRegistration())?.active?.postMessage("clear-user-data");
    } catch { /* no service worker: nothing cached to clear */ }
    return out;
  },
  me: () => get<User>("/api/auth/me"),
  topics: () => get<Topic[]>("/api/topics"),
  daily: () => get<Daily>("/api/quiz/daily"),
  active: () => get<ActiveSession[]>("/api/quiz/active"),
  startQuiz: (data: { mode: "daily" | "topic" | "mixed" | "current-affairs" | "review" | "weak" | "retry"; topic?: string; count?: number; day?: string; session?: string }) => post<QuizSession>("/api/quiz/start", data),
  reviewQueue: () => get<ReviewDue>("/api/me/review"),
  insights: () => get<Insights>("/api/me/insights"),
  answers: (opts: { topic?: string; only?: string; limit?: number; offset?: number } = {}) => {
    const p = new URLSearchParams();
    if (opts.topic) p.set("topic", opts.topic);
    if (opts.only && opts.only !== "all") p.set("only", opts.only);
    p.set("limit", String(opts.limit ?? 25));
    p.set("offset", String(opts.offset ?? 0));
    return get<Answers>(`/api/me/answers?${p}`);
  },
  prefs: () => get<Prefs>("/api/me/prefs"),
  savePrefs: (data: Partial<Pick<Prefs, "reminders_enabled" | "reminder_hour" | "reminder_minute" | "timezone">>) =>
    request<Prefs>("/api/me/prefs", { method: "PUT", body: JSON.stringify(data) }),
  pushSubscribe: (sub: { endpoint: string; p256dh: string; auth: string }) => post<Prefs>("/api/me/push/subscribe", sub),
  pushUnsubscribe: (sub: { endpoint: string; p256dh: string; auth: string }) => post<Prefs>("/api/me/push/unsubscribe", sub),
  pushTest: () => post<{ delivered: number }>("/api/me/push/test"),
  telegramLink: () => post<Prefs>("/api/me/telegram/link"),
  telegramUnlink: () => post<Prefs>("/api/me/telegram/unlink"),
  explain: (questionId: number) => post<{ question_id: number; explanation: string; cached: boolean }>(`/api/quiz/question/${questionId}/explain`),
  currentAffairs: (days = 7) => get<CurrentAffairs>(`/api/current-affairs?days=${days}`),
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
