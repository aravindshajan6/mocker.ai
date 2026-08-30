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
  streak_repaired: boolean;
  repairs_left: number;
  milestone: number | null;
  milestone_title: string | null;
  milestone_body: string | null;
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
  repairs_left: number;
  repairs_used: number;
  best_milestone: number;
  next_milestone: number | null;
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

export type ExamState = {
  id: string;
  questions: Question[];
  answers: Record<number, number>;
  marked: number[];
  seconds_remaining: number;
  duration_seconds: number;
  total: number;
  submitted: boolean;
};

export type ExamReviewRow = {
  question_id: number;
  number: number;
  text: string;
  options: string[];
  selected_index: number | null;
  correct_index: number;
  is_correct: boolean;
  skipped: boolean;
  explanation: string;
  topic: string;
  source_ref: string | null;
};

export type ExamTopicRow = { topic: string; icon: string; total: number; correct: number; wrong: number; blank: number };

export type ExamResult = {
  id: string;
  total: number;
  attempted: number;
  correct: number;
  wrong: number;
  blank: number;
  raw_score: number;
  marks_lost_to_negative: number;
  accuracy: number;
  percentage: number;
  points: number;
  time_taken_seconds: number;
  per_topic: ExamTopicRow[];
  guess_break_even: number;
  coaching: string;
  review: ExamReviewRow[];
};

export type ReviewDue = {
  due_now: number;
  due_today: number;
  learning: number;
  next_due_at: string | null;
  retention: number | null;
};

export type TopicInsight = {
  slug: string;
  name: string;
  icon: string;
  answered: number;
  correct: number;
  accuracy: number;
  recent_accuracy: number | null;
  trend: "improving" | "steady" | "slipping" | "new";
  coverage: number;
  question_count: number;
};

export type Insights = {
  topics: TopicInsight[];
  weakest: string[];
  strongest: string[];
  untouched: string[];
  overall_accuracy: number;
  answered_total: number;
  enough_data: boolean;
  headline: string;
};

export type Prefs = {
  reminders_enabled: boolean;
  reminder_hour: number;
  reminder_minute: number;
  timezone: string;
  push_devices: number;
  vapid_public_key: string;
  telegram_linked: boolean;
  telegram_available: boolean;
  telegram_link_url: string | null;
};

export type AnsweredQuestion = {
  question_id: number;
  text: string;
  options: string[];
  correct_index: number;
  selected_index: number;
  is_correct: boolean;
  explanation: string;
  topic: string;
  topic_slug: string;
  topic_icon: string;
  source_ref: string | null;
  source_url: string | null;
  difficulty: number;
  times_seen: number;
  times_correct: number;
  last_answered_at: string;
};

export type AnsweredTopic = {
  slug: string; name: string; icon: string; attempted: number; correct: number; wrong: number;
};

export type Answers = {
  topics: AnsweredTopic[];
  questions: AnsweredQuestion[];
  total: number;
  offset: number;
  limit: number;
};
