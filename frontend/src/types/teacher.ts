/**
 * Teacher-facing TypeScript types for the teacher ecosystem.
 */

export interface Teacher {
  id: string;
  email: string;
  name: string;
  school_name?: string;
  email_verified: boolean;
  digest_time: string;
  created_at: string;
}

export interface Classroom {
  id: string;
  teacher_id: string;
  name: string;
  grade_level: number;
  language: string;
  academic_year: string;
  student_count: number;
  created_at: string;
}

export interface StudentWithStats {
  id: string;
  classroom_id: string;
  display_name: string;
  roll_number?: string;
  grade_level: number;
  needs_attention: boolean;
  attention_reason?: string;
  created_at: string;
  // Analytics
  last_session_date?: string;
  latest_wcpm?: number;
  latest_accuracy?: number;
  session_count: number;
  best_delta?: number;
  top_error_types: string[];
}

export interface ErrorPatternSummary {
  error_type: string;
  count: number;
  percentage: number;
  example_words: string[];
}

export interface StudentAttentionCard {
  student_id: string;
  display_name: string;
  reason: string;
  latest_wcpm?: number;
  latest_accuracy?: number;
  top_errors: string[];
  sessions_without_improvement: number;
}

export interface ClassDashboard {
  classroom_id: string;
  classroom_name: string;
  grade_level: number;
  total_students: number;
  active_today: number;
  needs_attention_count: number;
  avg_wcpm: number;
  avg_accuracy: number;
  error_patterns: ErrorPatternSummary[];
  attention_students: StudentAttentionCard[];
  suggested_interventions: string[];
}

export interface PracticeSession {
  id: string;
  student_id: string;
  passage_id?: string;
  started_at: string;
  ended_at?: string;
  avg_wcpm: number;
  total_words_read: number;
  delta_summary?: Record<string, unknown>;
  completed_retest: boolean;
}
