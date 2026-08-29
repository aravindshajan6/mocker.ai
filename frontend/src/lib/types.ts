export type User = { id: string; name: string; email: string };

export type Topic = {
  slug: string;
  name: string;
  description: string;
  icon: string;
  question_count: number;
  answered: number;
  accuracy: number | null;
};

export type Question = {
  id: number;
  text: string;
  options: string[];
  difficulty: number;
  topic: string;
  topic_icon: string;
  published_at: string | null;
  source_ref: string | null;
};

export type AttemptState = {
  question_id: number;
  selected_index: number;
  is_correct: boolean;
  correct_index: number;
  explanation: string;
  points: number;
  source_url: string | null;
  source_ref: string | null;
};

export type QuizSession = {
  id: string;
  mode: "daily" | "topic" | "mixed" | "current-affairs";
  topic: string | null;
  questions: Question[];
  attempts: AttemptState[];
  score: number;
  correct: number;
  finished: boolean;
};

export type AnswerResult = {
  is_correct: boolean;
  correct_index: number;
  explanation: string;
  source_url: string | null;
  source_ref: string | null;
  points: number;
  combo: number;
  score: number;
  correct: number;
  answered: number;
  total: number;
  streak: number;
  streak_extended: boolean;
};

export type FinishResult = {
  score: number;
  bonus: number;
  correct: number;
  total: number;
  accuracy: number;
  total_points: number;
  level: number;
  level_title: string;
  points_to_next_level: number;
  streak: number;
  already_finished: boolean;
  new_badges: string[];
};

export type DayActivity = { day: string; answered: number; correct: number; points: number };

export type Stats = {
  total_points: number;
  level: number;
  level_title: string;
  level_progress: number;
  points_to_next_level: number;
  current_streak: number;
  longest_streak: number;
  questions_answered: number;
  correct_answers: number;
  accuracy: number;
  quizzes_completed: number;
  last_7_days: DayActivity[];
  daily_done_today: boolean;
  daily_score_today: number | null;
  badges: string[];
  badge_meta: Record<string, [string, string, string]>;
};

export type Daily = {
  day: string;
  size: number;
  done: boolean;
  session_id: string | null;
  score: number | null;
  correct: number | null;
};

export type HistoryRow = {
  id: string;
  mode: string;
  topic: string | null;
  topic_icon: string | null;
  finished_at: string | null;
  score: number;
  correct: number;
  total: number;
};

export type LeaderboardRow = { name: string; points: number; is_me: boolean };
export type ActiveSession = { id: string; mode: string; topic: string | null; topic_icon: string | null; answered: number; total: number };

export type CADay = { day: string; count: number; answered: number; session_id: string | null; finished: boolean; score: number | null };
export type CARun = { day: string; status: string; provider: string; model: string; fetched: number; generated: number; inserted: number; message: string; finished_at: string | null };
export type CurrentAffairs = { today: string; days: CADay[]; enabled: boolean; provider: string; has_key: boolean; last_run: CARun | null };
