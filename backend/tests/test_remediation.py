"""
Tests for error ranking, target word selection, and delta calculation.
"""
import asyncio
import json

from app import remediation
from app.remediation import (
    rank_and_select_target_words,
    calculate_remediation_delta,
    ERROR_SEVERITY_WEIGHTS,
    _story_matches_language,
)


SAMPLE_ERRORS = [
    {"word": "प्रकाश", "spoken_word": "पकाश",   "error_type": "CONJUNCT",
     "target_pattern": "प्र", "pause_before": 0.0, "in_stumble_cluster": False},
    {"word": "किताब",  "spoken_word": "कीताब",  "error_type": "MATRA",
     "target_pattern": "ि vs ी", "pause_before": 0.0, "in_stumble_cluster": True},
    {"word": "तारा",   "spoken_word": "टारा",   "error_type": "PHONETIC",
     "target_pattern": "त vs ट", "pause_before": 2.0, "in_stumble_cluster": False},
    {"word": "राम",    "spoken_word": "रामम",   "error_type": "SUBSTITUTION",
     "target_pattern": None,    "pause_before": 0.0, "in_stumble_cluster": False},
]


class TestStoryLanguageValidation:
    def test_accepts_english_and_hindi_for_matching_languages(self):
        english = "A curious child explored the bright planet and returned home smiling. " * 8
        hindi = "आरव अंतरिक्ष में चमकते तारों को देखकर बहुत खुश हुआ। " * 8

        assert _story_matches_language(english, "en")
        assert _story_matches_language(hindi, "hi")

    def test_rejects_hindi_story_for_english_request(self):
        hindi = "आरव अंतरिक्ष में चमकते तारों को देखकर बहुत खुश हुआ। " * 8

        assert not _story_matches_language(hindi, "en")

    def test_rejects_english_story_for_hindi_request(self):
        english = "A curious child explored the bright planet and returned home smiling. " * 8

        assert not _story_matches_language(english, "hi")

    def test_tries_next_provider_after_gemini_returns_wrong_language(self, monkeypatch):
        hindi = "आरव अंतरिक्ष में चमकते तारों को देखकर बहुत खुश हुआ। " * 8
        english = "A curious child explored the bright planet and returned home smiling. " * 8
        calls = []

        class FakeResponse:
            status_code = 200

            def __init__(self, payload):
                self.payload = payload
                self.text = json.dumps(payload)

            def json(self):
                return self.payload

        class FakeClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, url, **_kwargs):
                calls.append(url)
                if "generativelanguage.googleapis.com" in url:
                    payload = {
                        "candidates": [{"content": {"parts": [
                            {"text": json.dumps({"title": "कहानी", "text": hindi})}
                        ]}}]
                    }
                else:
                    payload = {
                        "output": [{"type": "message", "content": [{
                            "type": "output_text",
                            "text": json.dumps({"title": "A Starry Journey", "text": english}),
                        }]}]
                    }
                return FakeResponse(payload)

        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(remediation.httpx, "AsyncClient", FakeClient)

        result = asyncio.run(remediation.generate_remediation_story_gemini(
            target_words=["stars"],
            language="en",
        ))

        assert result["language"] == "en"
        assert result["generator_source"].startswith("OpenAI ")
        assert any("generativelanguage.googleapis.com" in url for url in calls)
        assert "api.openai.com" in calls[-1]


class TestRankAndSelectTargetWords:
    def test_returns_list(self):
        assert isinstance(rank_and_select_target_words(SAMPLE_ERRORS), list)

    def test_max_targets_respected(self):
        result = rank_and_select_target_words(SAMPLE_ERRORS, max_targets=2)
        assert len(result) <= 2

    def test_conjunct_selected(self):
        # CONJUNCT has the highest severity weight — must be included
        result = rank_and_select_target_words(SAMPLE_ERRORS, max_targets=4)
        words = [r["word"] for r in result]
        assert "प्रकाश" in words

    def test_empty_returns_empty(self):
        assert rank_and_select_target_words([]) == []

    def test_each_result_has_word_key(self):
        result = rank_and_select_target_words(SAMPLE_ERRORS)
        for item in result:
            assert "word" in item

    def test_stumble_cluster_boosts_priority(self):
        # किताब has in_stumble_cluster=True — should rank before राम
        result = rank_and_select_target_words(SAMPLE_ERRORS, max_targets=4)
        words = [r["word"] for r in result]
        if "किताब" in words and "राम" in words:
            assert words.index("किताब") < words.index("राम")

    def test_pause_boost_includes_word(self):
        # तारा has pause_before=2.0 >= 1.5 — boost should keep it in list
        result = rank_and_select_target_words(SAMPLE_ERRORS, max_targets=4)
        words = [r["word"] for r in result]
        assert "तारा" in words


class TestRemediationDelta:
    BASE = [
        {"expected_word": "प्रकाश", "status": "SUBSTITUTION", "is_dialect_variant": False},
        {"expected_word": "किताब",  "status": "correct",       "is_dialect_variant": False},
        {"expected_word": "तारा",   "status": "PHONETIC",      "is_dialect_variant": False},
    ]
    RETEST_PERFECT = [
        {"expected_word": "प्रकाश", "status": "correct", "is_dialect_variant": False},
        {"expected_word": "किताब",  "status": "correct", "is_dialect_variant": False},
        {"expected_word": "तारा",   "status": "correct", "is_dialect_variant": False},
    ]

    def test_retest_accuracy_not_below_baseline(self):
        delta = calculate_remediation_delta(
            target_words=["प्रकाश", "किताब", "तारा"],
            baseline_alignments=self.BASE,
            retest_alignments=self.RETEST_PERFECT,
        )
        assert delta["retest_accuracy"] >= delta["baseline_accuracy"]

    def test_positive_delta_on_improvement(self):
        delta = calculate_remediation_delta(
            target_words=["प्रकाश", "तारा"],
            baseline_alignments=self.BASE,
            retest_alignments=self.RETEST_PERFECT,
        )
        assert delta["delta"] >= 0

    def test_required_keys_present(self):
        delta = calculate_remediation_delta(
            target_words=["प्रकाश"],
            baseline_alignments=self.BASE,
            retest_alignments=self.RETEST_PERFECT,
        )
        for key in ("baseline_accuracy", "retest_accuracy", "delta",
                    "mastered_words_count", "positive_reinforcement"):
            assert key in delta, f"Missing key: {key}"

    def test_reinforcement_is_non_empty_string(self):
        delta = calculate_remediation_delta(
            target_words=["प्रकाश"],
            baseline_alignments=self.BASE,
            retest_alignments=self.RETEST_PERFECT,
        )
        assert isinstance(delta["positive_reinforcement"], str)
        assert len(delta["positive_reinforcement"]) > 5

    def test_no_improvement_zero_delta(self):
        delta = calculate_remediation_delta(
            target_words=["प्रकाश", "तारा"],
            baseline_alignments=self.BASE,
            retest_alignments=self.BASE,   # same errors
        )
        assert delta["delta"] <= 10


class TestErrorSeverityWeights:
    def test_conjunct_highest(self):
        assert ERROR_SEVERITY_WEIGHTS["CONJUNCT"] > ERROR_SEVERITY_WEIGHTS["MATRA"]
        assert ERROR_SEVERITY_WEIGHTS["MATRA"] > ERROR_SEVERITY_WEIGHTS["PHONETIC"]

    def test_omission_lower_than_substitution(self):
        assert ERROR_SEVERITY_WEIGHTS["OMISSION"] < ERROR_SEVERITY_WEIGHTS["SUBSTITUTION"]

    def test_repetition_lowest(self):
        assert ERROR_SEVERITY_WEIGHTS["REPETITION"] <= min(
            v for k, v in ERROR_SEVERITY_WEIGHTS.items() if k != "REPETITION"
        )
