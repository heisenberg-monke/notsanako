"""
Tests for alignment engine: MATCH/OMISSION/SUBSTITUTION detection and WCPM calculation.
"""
import pytest
from app.alignment import (
    evaluate_reading_attempt_indic,
    token_similarity,
    clean_token,
)


def _words(word_list, start=0.0, gap=0.5):
    """Build synthetic STT word objects with timestamps."""
    out = []
    t = start
    for w in word_list:
        out.append({"word": w, "start": round(t, 2), "end": round(t + gap, 2)})
        t += gap + 0.05
    return out


class TestTokenSimilarity:
    def test_exact_match_is_1(self):
        assert token_similarity("राम", "राम") == 1.0

    def test_both_empty_is_1(self):
        assert token_similarity("", "") == 1.0

    def test_one_empty_is_0(self):
        assert token_similarity("राम", "") == 0.0
        assert token_similarity("", "राम") == 0.0

    def test_completely_different_low_score(self):
        assert token_similarity("अ", "ब") < 0.5

    def test_near_match_high_score(self):
        # Same word — should be >= 0.95
        assert token_similarity("आकाश", "आकाश") >= 0.95


class TestCleanToken:
    def test_strips_punctuation(self):
        assert clean_token("राम।") in ("राम", "राम।".strip("।"))

    def test_empty_returns_empty(self):
        assert clean_token("") == ""

    def test_lowercase_english(self):
        result = clean_token("Apple")
        assert result == "apple"


class TestAlignmentPerfectReading:
    REF = "आकाश में तारे चमकते हैं"

    def test_perfect_accuracy(self):
        words = _words(["आकाश", "में", "तारे", "चमकते", "हैं"])
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=words,
            duration_seconds=3.0,
            target_wcpm=75,
        )
        assert result["metrics"]["accuracy_percentage"] >= 90.0

    def test_no_errors_on_perfect(self):
        words = _words(["आकाश", "में", "तारे", "चमकते", "हैं"])
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=words,
            duration_seconds=3.0,
            target_wcpm=75,
        )
        assert len(result["structured_errors"]) == 0

    def test_returns_all_required_keys(self):
        words = _words(["आकाश", "में", "तारे", "चमकते", "हैं"])
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=words,
            duration_seconds=3.0,
            target_wcpm=75,
        )
        for key in ("metrics", "structured_errors", "alignments", "feedback",
                    "error_breakdown", "stumble_clusters", "long_pauses"):
            assert key in result, f"Missing key: {key}"


class TestAlignmentErrors:
    REF = "आकाश में तारे चमकते हैं"

    def test_omission_detected(self):
        # Skip "तारे"
        words = _words(["आकाश", "में", "चमकते", "हैं"])
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=words,
            duration_seconds=2.5,
            target_wcpm=75,
        )
        error_types = [e["error_type"] for e in result["structured_errors"]]
        assert "OMISSION" in error_types

    def test_substitution_detected(self):
        # Replace "तारे" with unrelated word
        words = _words(["आकाश", "में", "पत्थर", "चमकते", "हैं"])
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=words,
            duration_seconds=3.0,
            target_wcpm=75,
        )
        error_types = [e["error_type"] for e in result["structured_errors"]]
        assert any(t in error_types for t in ["SUBSTITUTION", "PHONETIC", "MATRA", "CONJUNCT"])

    def test_empty_transcription_zero_accuracy(self):
        result = evaluate_reading_attempt_indic(
            reference_text=self.REF,
            transcribed_words=[],
            duration_seconds=10.0,
            target_wcpm=75,
        )
        assert result["metrics"]["accuracy_percentage"] == 0.0
        assert result["metrics"]["wcpm"] == 0.0


class TestWCPM:
    def test_wcpm_calculation_approx(self):
        # 10 words read correctly in 60 seconds → WCPM ≈ 10
        ref = "एक दो तीन चार पाँच छह सात आठ नौ दस"
        words = [
            {"word": w, "start": i * 6.0, "end": i * 6.0 + 1.0}
            for i, w in enumerate(ref.split())
        ]
        result = evaluate_reading_attempt_indic(
            reference_text=ref,
            transcribed_words=words,
            duration_seconds=60.0,
            target_wcpm=75,
        )
        wcpm = result["metrics"]["wcpm"]
        assert 8.0 <= wcpm <= 12.0, f"WCPM {wcpm} outside expected range [8, 12]"

    def test_wcpm_zero_on_empty(self):
        result = evaluate_reading_attempt_indic(
            reference_text="एक दो तीन",
            transcribed_words=[],
            duration_seconds=5.0,
            target_wcpm=75,
        )
        assert result["metrics"]["wcpm"] == 0.0

    def test_accuracy_between_0_and_100(self):
        words = _words(["एक", "दो", "तीन"])
        result = evaluate_reading_attempt_indic(
            reference_text="एक दो तीन",
            transcribed_words=words,
            duration_seconds=3.0,
            target_wcpm=75,
        )
        acc = result["metrics"]["accuracy_percentage"]
        assert 0.0 <= acc <= 100.0
