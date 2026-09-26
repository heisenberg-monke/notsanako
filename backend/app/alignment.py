"""
Enhanced Indic Word-Level Sequence Alignment and Oral Reading Diagnostic Engine.
Performs:
1. Word-level dynamic programming alignment (Needleman-Wunsch with Indic phonetics)
2. Detection of pauses longer than 1.5 seconds (Hesitations)
3. Detection of 3+ consecutive error / stumbling clusters ("Tongue Twister" lines)
4. Granular error classification into:
   - MATRA (vowel length & diacritic confusion, e.g., इ/ई, उ/ऊ)
   - CONJUNCT (sanyuktakshar clusters, e.g., प्र, क्ष, त्र, ज्ञ, स्त)
   - PHONETIC (dental vs retroflex त/ट, aspiration shifts क/ख)
   - OMISSION (skipped words)
   - REPETITION (stutters or self-corrections)
   - DIALECT_EQUIVALENT (regional accents like Eastern /b/ for /v/ - dialect-fair)
5. WCPM (Words Correct Per Minute) calculation
6. Structured, non-diagnostic pedagogical error records
"""

import re
import unicodedata
from typing import List, Dict, Any, Tuple, Optional
import Levenshtein

from app.indic_rules import (
    normalize_devanagari,
    classify_indic_error,
    check_dialect_equivalence,
    has_conjunct
)


def clean_token(token: str) -> str:
    """Clean a token for semantic comparison (strip punctuation and normalize)."""
    if not token:
        return ""
    norm = normalize_devanagari(token)
    cleaned = re.sub(r'^[^\w\u0900-\u097F]+|[^\w\u0900-\u097F]+$', '', norm)
    return cleaned.lower()


def token_similarity(ref: str, hyp: str) -> float:
    """Calculate phonetic/orthographic similarity ratio between two tokens."""
    ref_c = clean_token(ref)
    hyp_c = clean_token(hyp)

    if not ref_c and not hyp_c:
        return 1.0
    if not ref_c or not hyp_c:
        return 0.0

    if ref_c == hyp_c:
        return 1.0

    # Check dialect equivalence before standard Levenshtein
    dialect_check = check_dialect_equivalence(ref_c, hyp_c)
    if dialect_check:
        return 0.98  # Highly scoring dialect-fair equivalent

    # Calculate Levenshtein ratio
    ratio = Levenshtein.ratio(ref_c, hyp_c)
    return ratio


def align_tokens_with_timings(
    reference_tokens: List[str],
    hypothesis_words: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Align reference tokens with transcribed words containing timestamps.
    hypothesis_words: [{"word": "...", "start": 0.5, "end": 1.1}, ...]
    """
    n = len(reference_tokens)
    m = len(hypothesis_words)

    # DP score matrix and traceback matrix
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    trace = [[0] * (m + 1) for _ in range(n + 1)]

    gap_penalty = -1.0
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap_penalty
        trace[i][0] = 2  # Omission from reference

    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap_penalty
        trace[0][j] = 3  # Insertion into hypothesis

    for i in range(1, n + 1):
        ref_word = reference_tokens[i - 1]
        for j in range(1, m + 1):
            hyp_word_obj = hypothesis_words[j - 1]
            hyp_word = hyp_word_obj.get("word", "")
            sim = token_similarity(ref_word, hyp_word)

            if sim >= 0.82:
                match_score = 2.0 * sim
            elif sim >= 0.60:
                match_score = 0.5 * sim
            else:
                match_score = -0.8

            score_diag = dp[i - 1][j - 1] + match_score
            score_up = dp[i - 1][j] + gap_penalty
            score_left = dp[i][j - 1] + gap_penalty

            best = max(score_diag, score_up, score_left)
            dp[i][j] = best

            if best == score_diag:
                trace[i][j] = 1
            elif best == score_up:
                trace[i][j] = 2
            else:
                trace[i][j] = 3

    # Backtracking
    i, j = n, m
    rev_steps: List[Tuple[int, Optional[str], Optional[Dict[str, Any]], float]] = []

    while i > 0 or j > 0:
        step = trace[i][j]
        if i > 0 and j > 0 and step == 1:
            ref_w = reference_tokens[i - 1]
            hyp_obj = hypothesis_words[j - 1]
            sim = token_similarity(ref_w, hyp_obj.get("word", ""))
            rev_steps.append((1, ref_w, hyp_obj, sim))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or step == 2):
            ref_w = reference_tokens[i - 1]
            rev_steps.append((2, ref_w, None, 0.0))
            i -= 1
        elif j > 0 and (i == 0 or step == 3):
            hyp_obj = hypothesis_words[j - 1]
            rev_steps.append((3, None, hyp_obj, 0.0))
            j -= 1

    rev_steps.reverse()

    aligned: List[Dict[str, Any]] = []
    current_index = 0
    prev_end_time: Optional[float] = None

    for action, ref_w, hyp_obj, sim in rev_steps:
        hyp_w = hyp_obj.get("word", "") if hyp_obj else None
        start_t = hyp_obj.get("start") if hyp_obj else None
        end_t = hyp_obj.get("end") if hyp_obj else None

        # Check for pause before this word (> 1.5s)
        pause_before = 0.0
        if start_t is not None and prev_end_time is not None:
            gap = start_t - prev_end_time
            if gap >= 1.5:
                pause_before = round(gap, 2)

        if end_t is not None:
            prev_end_time = end_t

        if action == 1:
            # Check for repetition (student repeating the same word)
            is_repetition = False
            if len(aligned) > 0 and aligned[-1].get("expected_word") == ref_w:
                is_repetition = True

            # Match or Substitution
            if sim >= 0.85:
                # Accurately read
                aligned.append({
                    "index": current_index,
                    "expected_word": ref_w,
                    "spoken_word": hyp_w,
                    "status": "correct",
                    "error_type": "CORRECT",
                    "is_dialect_variant": False,
                    "similarity": round(sim, 2),
                    "start_time": start_t,
                    "end_time": end_t,
                    "pause_before": pause_before,
                    "notes": "Accurately read"
                })
            else:
                # Classify linguistic error via Indic rules engine
                diagnosis = classify_indic_error(ref_w or "", hyp_w)
                
                # If accepted as dialect equivalent, treat status as correct with dialect flag
                if diagnosis.get("is_dialect_variant"):
                    aligned.append({
                        "index": current_index,
                        "expected_word": ref_w,
                        "spoken_word": hyp_w,
                        "status": "correct",
                        "error_type": "DIALECT_EQUIVALENT",
                        "is_dialect_variant": True,
                        "target_pattern": diagnosis.get("target_pattern"),
                        "linguistic_detail": diagnosis.get("linguistic_detail"),
                        "pedagogical_remedy": diagnosis.get("pedagogical_remedy"),
                        "similarity": round(sim, 2),
                        "start_time": start_t,
                        "end_time": end_t,
                        "pause_before": pause_before,
                        "notes": "Dialect variant accepted"
                    })
                else:
                    err_type = "REPETITION" if is_repetition else diagnosis.get("error_type", "SUBSTITUTION")
                    aligned.append({
                        "index": current_index,
                        "expected_word": ref_w,
                        "spoken_word": hyp_w,
                        "status": "substitution",
                        "error_type": err_type,
                        "is_dialect_variant": False,
                        "target_pattern": diagnosis.get("target_pattern"),
                        "linguistic_detail": diagnosis.get("linguistic_detail"),
                        "pedagogical_remedy": diagnosis.get("pedagogical_remedy"),
                        "similarity": round(sim, 2),
                        "start_time": start_t,
                        "end_time": end_t,
                        "pause_before": pause_before,
                        "notes": f"Read as '{hyp_w}' instead of '{ref_w}'"
                    })
            current_index += 1

        elif action == 2:
            # Omission (word skipped)
            diagnosis = classify_indic_error(ref_w or "", None)
            aligned.append({
                "index": current_index,
                "expected_word": ref_w,
                "spoken_word": None,
                "status": "omission",
                "error_type": "OMISSION",
                "is_dialect_variant": False,
                "target_pattern": ref_w,
                "linguistic_detail": diagnosis.get("linguistic_detail"),
                "pedagogical_remedy": diagnosis.get("pedagogical_remedy"),
                "similarity": 0.0,
                "start_time": None,
                "end_time": None,
                "pause_before": 0.0,
                "notes": f"Skipped word '{ref_w}'"
            })
            current_index += 1

        elif action == 3:
            # Insertion or Repetition
            aligned.append({
                "index": current_index,
                "expected_word": None,
                "spoken_word": hyp_w,
                "status": "insertion",
                "error_type": "INSERTION",
                "is_dialect_variant": False,
                "target_pattern": hyp_w,
                "linguistic_detail": f"Extra spoken word '{hyp_w}'.",
                "pedagogical_remedy": "Practice steady pacing without rushing ahead.",
                "similarity": 0.0,
                "start_time": start_t,
                "end_time": end_t,
                "pause_before": pause_before,
                "notes": f"Extra word '{hyp_w}'"
            })

    return aligned


def detect_stumble_clusters(
    alignments: List[Dict[str, Any]],
    cluster_threshold: int = 3
) -> List[Dict[str, Any]]:
    """
    Detects clusters of 3+ consecutive errors/hesitations (stumble clusters).
    Marks individual word items with 'in_stumble_cluster' = True and returns cluster info.
    """
    clusters = []
    current_run = []

    for idx, item in enumerate(alignments):
        # An item counts toward a struggle cluster if it is an error (substitution, omission)
        # or had a severe pause > 1.5s
        is_struggle = (
            item["status"] in ("substitution", "omission")
            or item.get("pause_before", 0) >= 1.5
        )

        if is_struggle:
            current_run.append(idx)
        else:
            if len(current_run) >= cluster_threshold:
                clusters.append(list(current_run))
            current_run = []

    if len(current_run) >= cluster_threshold:
        clusters.append(list(current_run))

    # Mark tokens in alignments
    cluster_records = []
    for c_idx, indices in enumerate(clusters):
        words_in_cluster = []
        for i in indices:
            alignments[i]["in_stumble_cluster"] = True
            alignments[i]["cluster_id"] = c_idx + 1
            w = alignments[i].get("expected_word") or alignments[i].get("spoken_word")
            if w:
                words_in_cluster.append(w)

        cluster_records.append({
            "cluster_id": c_idx + 1,
            "word_count": len(indices),
            "words": words_in_cluster,
            "phrase_snippet": " ".join(words_in_cluster),
            "rationale": f"Cluster of {len(indices)} consecutive struggle/hesitation points ('tongue-twister' line)."
        })

    return cluster_records


def evaluate_reading_attempt_indic(
    reference_text: str,
    transcribed_words: List[Dict[str, Any]],
    duration_seconds: float,
    target_wcpm: int = 80
) -> Dict[str, Any]:
    """
    Full oral reading evaluation for Indian school contexts:
    - Word-level DP alignment
    - Hesitation pauses (> 1.5s)
    - 3+ struggle clusters
    - Error breakdown (MATRA, CONJUNCT, PHONETIC, OMISSION, REPETITION, DIALECT_EQUIVALENT)
    - WCPM & Accuracy
    - Structured error records for pedagogical intervention
    """
    norm_ref = normalize_devanagari(reference_text)
    ref_tokens = norm_ref.split() if norm_ref else []

    duration_seconds = max(duration_seconds, 1.0)
    duration_minutes = duration_seconds / 60.0

    if not ref_tokens:
        return {
            "alignments": [],
            "metrics": {},
            "error_breakdown": {},
            "structured_errors": [],
            "stumble_clusters": [],
            "long_pauses": [],
            "feedback": "No passage text provided."
        }

    # 1. Align tokens
    alignments = align_tokens_with_timings(ref_tokens, transcribed_words)

    # 2. Detect 3+ consecutive stumbling clusters
    stumble_clusters = detect_stumble_clusters(alignments, cluster_threshold=3)

    # 3. Detect long pauses (> 1.5 seconds)
    long_pauses = []
    for item in alignments:
        p_sec = item.get("pause_before", 0.0)
        if p_sec >= 1.5:
            long_pauses.append({
                "word": item.get("expected_word") or item.get("spoken_word"),
                "pause_duration_seconds": p_sec,
                "timestamp": item.get("start_time"),
                "note": f"Hesitation pause of {p_sec}s before '{item.get('expected_word')}'"
            })

    # 4. Count errors and categorize
    correct_count = sum(1 for item in alignments if item["status"] == "correct")
    dialect_count = sum(1 for item in alignments if item.get("error_type") == "DIALECT_EQUIVALENT")
    matra_count = sum(1 for item in alignments if item.get("error_type") == "MATRA")
    conjunct_count = sum(1 for item in alignments if item.get("error_type") == "CONJUNCT")
    phonetic_count = sum(1 for item in alignments if item.get("error_type") == "PHONETIC")
    omission_count = sum(1 for item in alignments if item.get("error_type") == "OMISSION")
    repetition_count = sum(1 for item in alignments if item.get("error_type") == "REPETITION")
    substitution_count = sum(1 for item in alignments if item["status"] == "substitution" and item.get("error_type") not in ("MATRA", "CONJUNCT", "PHONETIC", "REPETITION"))
    insertion_count = sum(1 for item in alignments if item["status"] == "insertion")

    total_expected = len(ref_tokens)
    total_spoken = len(transcribed_words)

    # Accuracy percentage (dialect-fair: dialect variants count as correct)
    accuracy_pct = round((correct_count / max(total_expected, 1)) * 100.0, 1)

    # WCPM (Words Correct Per Minute)
    wcpm = round(correct_count / duration_minutes, 1)
    wpm = round(total_spoken / duration_minutes, 1)

    # 5. Build structured error records (identifying WHAT and WHY)
    structured_errors = []
    for item in alignments:
        if item["status"] in ("substitution", "omission") and not item.get("is_dialect_variant"):
            structured_errors.append({
                "word": item.get("expected_word"),
                "spoken_word": item.get("spoken_word"),
                "error_type": item.get("error_type", "SUBSTITUTION"),
                "target_pattern": item.get("target_pattern"),
                "linguistic_detail": item.get("linguistic_detail"),
                "pedagogical_remedy": item.get("pedagogical_remedy"),
                "pause_before": item.get("pause_before", 0.0),
                "in_stumble_cluster": item.get("in_stumble_cluster", False),
                "timestamp_start": item.get("start_time"),
                "timestamp_end": item.get("end_time"),
            })

    # 6. Pedagogical Feedback (strictly non-diagnostic)
    feedback_points = []
    if accuracy_pct >= 90 and wcpm >= target_wcpm * 0.9:
        rating = "Fluent Confident Reader"
        feedback_points.append("Excellent oral reading rhythm and strong foundational decoding!")
    elif accuracy_pct >= 75:
        rating = "Developing Reader"
        feedback_points.append("Commendable reading effort! With a little targeted practice on specific word patterns, fluency will soar.")
    else:
        rating = "Emerging Reader"
        feedback_points.append("Great start! Regular guided reading practice builds word recognition and confidence.")

    if matra_count > 0:
        feedback_points.append(f"Noticed {matra_count} vowel length (matra) variations. Practice distinguishing short vs. long vowel duration.")
    if conjunct_count > 0:
        feedback_points.append(f"Encountered {conjunct_count} conjunct letter (sanyuktakshar) clusters. Blending half-letters smoothly will boost pace.")
    if len(long_pauses) > 0:
        feedback_points.append(f"Recorded {len(long_pauses)} hesitation pause(s) over 1.5s where taking a deep breath and chunking words can help.")
    if dialect_count > 0:
        feedback_points.append(f"Embraced {dialect_count} regional pronunciation variation(s) under our dialect-fair evaluation.")

    pedagogical_feedback = " ".join(feedback_points)

    return {
        "alignments": alignments,
        "metrics": {
            "accuracy_percentage": accuracy_pct,
            "wcpm": wcpm,
            "wpm": wpm,
            "target_wcpm": target_wcpm,
            "duration_seconds": round(duration_seconds, 1),
            "total_expected_words": total_expected,
            "total_spoken_words": total_spoken,
            "correct_count": correct_count,
            "error_count": len(structured_errors),
            "rating": rating
        },
        "error_breakdown": {
            "matra_errors": matra_count,
            "conjunct_errors": conjunct_count,
            "phonetic_errors": phonetic_count,
            "omission_errors": omission_count,
            "repetition_errors": repetition_count,
            "general_substitution_errors": substitution_count,
            "insertion_errors": insertion_count,
            "dialect_variants_accepted": dialect_count,
            "long_pauses_count": len(long_pauses),
            "stumble_clusters_count": len(stumble_clusters)
        },
        "structured_errors": structured_errors,
        "stumble_clusters": stumble_clusters,
        "long_pauses": long_pauses,
        "feedback": pedagogical_feedback
    }
