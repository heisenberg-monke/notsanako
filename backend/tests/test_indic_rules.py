"""
Tests for Indic linguistic rules:
MATRA vowel confusion, CONJUNCT detection, PHONETIC pairs, DIALECT_EQUIVALENT fairness.
"""
import pytest
from app.indic_rules import (
    normalize_devanagari,
    classify_indic_error,
    check_dialect_equivalence,
    has_conjunct,
)


class TestNormalizeDevanagari:
    def test_idempotent(self):
        word = "आकाश"
        assert normalize_devanagari(normalize_devanagari(word)) == normalize_devanagari(word)

    def test_handles_empty(self):
        assert normalize_devanagari("") == ""

    def test_non_empty_result(self):
        result = normalize_devanagari("प्रकाश")
        assert len(result) > 0

    def test_returns_string(self):
        assert isinstance(normalize_devanagari("राम"), str)


class TestMatraClassification:
    """Vowel length confusion — short/long matra pairs."""

    def test_short_i_vs_long_ee(self):
        # ि (short i) vs ी (long ee)
        ref = "किताब"   # short i
        hyp = "कीताब"   # long ee — matra error
        result = classify_indic_error(ref, hyp)
        assert result["error_type"] == "MATRA", f"Expected MATRA, got {result}"

    def test_short_u_vs_long_oo(self):
        ref = "सुना"    # short u
        hyp = "सूना"    # long oo
        result = classify_indic_error(ref, hyp)
        assert result["error_type"] == "MATRA", f"Expected MATRA, got {result}"

    def test_exact_match_high_similarity(self):
        ref = "किताब"
        hyp = "किताब"
        result = classify_indic_error(ref, hyp)
        # Either MATCH or similarity >= 0.9
        assert result["error_type"] == "MATCH" or result.get("similarity", 0) >= 0.9


class TestConjunctClassification:
    """Consonant cluster / sanyuktakshar detection."""

    def test_has_conjunct_pra(self):
        assert has_conjunct("प्रकाश") is True

    def test_has_conjunct_ksha(self):
        assert has_conjunct("क्षमा") is True

    def test_no_conjunct_simple(self):
        assert has_conjunct("राम") is False

    def test_no_conjunct_empty(self):
        assert has_conjunct("") is False

    def test_conjunct_drop_classified(self):
        # Dropping the pr- conjunct should be classified as CONJUNCT or SUBSTITUTION
        ref = "प्रकाश"
        hyp = "पकाश"
        result = classify_indic_error(ref, hyp)
        assert result["error_type"] in ("CONJUNCT", "SUBSTITUTION", "PHONETIC")


class TestPhoneticClassification:
    """Dental vs retroflex and aspiration confusion."""

    def test_dental_vs_retroflex_t(self):
        ref = "तारा"    # dental त
        hyp = "टारा"    # retroflex ट
        result = classify_indic_error(ref, hyp)
        assert result["error_type"] in ("PHONETIC", "SUBSTITUTION")

    def test_unaspirated_vs_aspirated_k(self):
        ref = "काम"     # unaspirated क
        hyp = "खाम"     # aspirated ख
        result = classify_indic_error(ref, hyp)
        assert result["error_type"] in ("PHONETIC", "SUBSTITUTION")

    def test_result_has_required_keys(self):
        result = classify_indic_error("राम", "दाम")
        assert "error_type" in result


class TestDialectEquivalence:
    """Regional dialect fairness — should not unfairly penalise students."""

    def test_v_b_equivalence(self):
        # Eastern dialects: /v/ → /b/
        result = check_dialect_equivalence("वन", "बन")
        assert isinstance(result, bool)  # must not crash

    def test_returns_bool(self):
        result = check_dialect_equivalence("साथ", "शाथ")
        assert isinstance(result, bool)

    def test_identical_not_dialect_error(self):
        # Exact match should return without error
        result = check_dialect_equivalence("राम", "राम")
        assert isinstance(result, bool)
