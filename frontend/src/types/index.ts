export type WordStatus = 'unread' | 'correct' | 'substitution' | 'omission' | 'insertion';

export type ErrorType = 
  | 'CORRECT'
  | 'MATRA'
  | 'CONJUNCT'
  | 'PHONETIC'
  | 'OMISSION'
  | 'REPETITION'
  | 'INSERTION'
  | 'DIALECT_EQUIVALENT'
  | 'SUBSTITUTION';

export interface Passage {
  id: string;
  title: string;
  grade_level: number;
  language: 'en' | 'hi';
  target_wcpm: number;
  description: string;
  text: string;
  difficulty: 'Easy' | 'Medium' | 'Challenging';
  key_vocabulary: string[];
}

export interface WordAlignment {
  index: number;
  expected_word: string | null;
  spoken_word: string | null;
  status: WordStatus;
  error_type?: ErrorType;
  is_dialect_variant?: boolean;
  target_pattern?: string;
  linguistic_detail?: string;
  pedagogical_remedy?: string;
  similarity: number;
  pause_before?: number;
  in_stumble_cluster?: boolean;
  cluster_id?: number;
  start_time?: number | null;
  end_time?: number | null;
  notes?: string;
}

export interface StructuredErrorRecord {
  word: string;
  spoken_word: string | null;
  error_type: ErrorType;
  target_pattern: string;
  linguistic_detail: string;
  pedagogical_remedy: string;
  pause_before: number;
  in_stumble_cluster: boolean;
  timestamp_start?: number | null;
  timestamp_end?: number | null;
}

export interface PriorityTargetWord {
  word: string;
  error_type: string;
  frequency: number;
  total_score: number;
  target_pattern?: string;
  linguistic_detail?: string;
  pedagogical_remedy?: string;
}

export interface StumbleCluster {
  cluster_id: number;
  word_count: number;
  words: string[];
  phrase_snippet: string;
  rationale: string;
}

export interface LongPause {
  word: string;
  pause_duration_seconds: number;
  timestamp?: number | null;
  note: string;
}

export interface ErrorBreakdown {
  matra_errors: number;
  conjunct_errors: number;
  phonetic_errors: number;
  omission_errors: number;
  repetition_errors: number;
  general_substitution_errors: number;
  insertion_errors: number;
  dialect_variants_accepted: number;
  long_pauses_count: number;
  stumble_clusters_count: number;
}

export interface ReadingMetrics {
  accuracy_percentage: number;
  wcpm: number;
  wpm: number;
  target_wcpm: number;
  duration_seconds: number;
  total_expected_words: number;
  total_spoken_words: number;
  correct_count: number;
  error_count: number;
  rating: string;
}

export interface ReadingAnalysis {
  session_id?: number;
  passage_id: string;
  passage_title: string;
  language: string;
  reference_text: string;
  transcribed_text: string;
  alignments: WordAlignment[];
  metrics: ReadingMetrics;
  error_breakdown: ErrorBreakdown;
  structured_errors: StructuredErrorRecord[];
  priority_target_words?: PriorityTargetWord[];
  stumble_clusters: StumbleCluster[];
  long_pauses: LongPause[];
  feedback: string;
}

export interface TargetWordOccurrence {
  word: string;
  occurrences_count: number;
  sentence_indices: number[];
}

export interface RemediationPassage {
  title: string;
  text: string;
  sentences: string[];
  target_word_occurrences: TargetWordOccurrence[];
  word_count: number;
  theme: string;
  grade_level: number;
  language: string;
  generator_source?: string;
}

export interface WordMasteryItem {
  word: string;
  baseline_correct: boolean;
  retest_correct: boolean;
  mastered: boolean;
}

export interface DeltaSummary {
  target_words: string[];
  baseline_accuracy: number;
  retest_accuracy: number;
  delta: number;
  mastered_words_count: number;
  total_target_words: number;
  word_mastery_breakdown: WordMasteryItem[];
  positive_reinforcement: string;
}

export interface RetestEvaluationResult {
  retest_id: number;
  transcribed_text: string;
  retest_alignments: WordAlignment[];
  retest_metrics: ReadingMetrics;
  delta_summary: DeltaSummary;
  positive_reinforcement: string;
}

/** Preview returned by the adaptive passage generation step */
export interface AdaptiveRemediationPreview {
  target_words: string[];
  grade_level: number;
  remediation_story: string;
  prompt_context: string;
  source?: string;
}
