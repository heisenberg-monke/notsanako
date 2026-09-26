"""
End-to-end integration tests: health, passages, consent, telemetry, and
full baseline → remediation → retest loop with all external APIs mocked.
"""
import io
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Fake data ────────────────────────────────────────────────────────────────

FAKE_STT_RESULT = {
    "text": "आकाश में तारे चमकते हैं",
    "words": [
        {"word": "आकाश",   "start": 0.0, "end": 0.5},
        {"word": "में",     "start": 0.6, "end": 0.8},
        {"word": "तारे",    "start": 0.9, "end": 1.2},
        {"word": "चमकते",  "start": 1.3, "end": 1.7},
        {"word": "हैं",     "start": 1.8, "end": 2.0},
    ],
}

FAKE_STORY = {
    "title": "प्रकाश का सफर",
    "text": "प्रकाश ने आकाश में तारे देखे। वह बहुत खुश हुआ।",
    "sentences": ["प्रकाश ने आकाश में तारे देखे।", "वह बहुत खुश हुआ।"],
    "target_word_occurrences": [
        {"word": "प्रकाश", "occurrences_count": 1, "sentence_indices": [0]}
    ],
    "word_count": 10,
    "theme": "space",
    "grade_level": 4,
    "language": "hi",
    "generator_source": "Gemini 1.5 Flash",
}

# Minimal WebM-like bytes with sufficient variance (not all-zero silence)
FAKE_AUDIO = b"\x1a\x45\xdf\xa3" + bytes((i % 200) + 28 for i in range(3500))


# ── Health & basic endpoints ─────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_has_status_field(self, client):
        data = client.get("/api/health").json()
        assert "status" in data

    def test_audio_retention_policy_in_response(self, client):
        data = client.get("/api/health").json()
        assert "audio_retention_policy" in data
        assert "zero" in data["audio_retention_policy"].lower()

    def test_consent_api_enabled(self, client):
        data = client.get("/api/health").json()
        assert data.get("dpdp_consent_api") == "enabled"


class TestPassageEndpoints:
    def test_list_returns_list(self, client):
        r = client.get("/api/passages")
        assert r.status_code == 200
        assert "passages" in r.json()

    def test_filter_by_language(self, client):
        r = client.get("/api/passages?language=hi")
        assert r.status_code == 200

    def test_get_passage_invalid_id(self, client):
        r = client.get("/api/passages/does-not-exist-xyz")
        assert r.status_code == 404

    def test_get_passage_valid(self, client):
        passages = client.get("/api/passages").json().get("passages", [])
        if not passages:
            pytest.skip("No passages available")
        pid = passages[0]["id"]
        r = client.get(f"/api/passages/{pid}")
        assert r.status_code == 200


class TestConsentEndpoints:
    def test_grant_consent(self, client):
        r = client.post("/api/consent/grant", json={
            "student_id": "student-consent-test",
            "given_by": "Rajesh Sharma",
            "given_by_relation": "parent",
        })
        assert r.status_code == 200
        assert r.json()["status"] in ("granted", "already_active")

    def test_consent_status_active_after_grant(self, client):
        sid = "student-status-check"
        client.post("/api/consent/grant", json={
            "student_id": sid, "given_by": "Priya Patel",
        })
        r = client.get(f"/api/consent/status/{sid}")
        assert r.status_code == 200
        assert r.json()["consent_active"] is True

    def test_revoke_consent(self, client):
        sid = "student-revoke-check"
        client.post("/api/consent/grant", json={
            "student_id": sid, "given_by": "Mohan Das",
        })
        r = client.post(f"/api/consent/revoke/{sid}")
        assert r.status_code == 200
        assert r.json()["status"] == "revoked"

    def test_revoke_non_existent_returns_404(self, client):
        r = client.post("/api/consent/revoke/student-never-existed-xyz")
        assert r.status_code == 404

    def test_double_grant_returns_already_active(self, client):
        sid = "student-double-grant"
        client.post("/api/consent/grant", json={"student_id": sid, "given_by": "A"})
        r = client.post("/api/consent/grant", json={"student_id": sid, "given_by": "A"})
        assert r.json()["status"] == "already_active"


class TestTelemetryEndpoints:
    def test_record_event(self, client):
        r = client.post("/api/telemetry", json={
            "event_type": "session_complete",
            "student_id": "student-1",
            "classroom_id": "default-class-1",
            "wcpm": 55.5,
            "accuracy_pct": 82.0,
            "language": "hi",
            "grade_level": 4,
            "error_type_counts": {"MATRA": 3, "CONJUNCT": 2},
        })
        assert r.status_code == 200
        assert "event_id" in r.json()

    def test_summary_returns_aggregate(self, client):
        # Record an event first
        client.post("/api/telemetry", json={
            "event_type": "session_complete",
            "classroom_id": "default-class-1",
            "wcpm": 60.0,
            "accuracy_pct": 85.0,
        })
        r = client.get("/api/telemetry/summary?classroom_id=default-class-1")
        assert r.status_code == 200
        data = r.json()
        assert "total_events" in data
        assert data["total_events"] >= 1


class TestAnalyzeReadingEndpoint:
    def test_no_audio_returns_400(self, client):
        passages = client.get("/api/passages?language=hi").json().get("passages", [])
        if not passages:
            pytest.skip("No Hindi passages")
        pid = passages[0]["id"]
        r = client.post("/api/analyze-reading", data={
            "passage_id": pid, "duration_seconds": "30",
        })
        assert r.status_code == 400

    def test_tiny_audio_returns_4xx(self, client):
        passages = client.get("/api/passages?language=hi").json().get("passages", [])
        if not passages:
            pytest.skip("No Hindi passages")
        pid = passages[0]["id"]
        r = client.post(
            "/api/analyze-reading",
            data={"passage_id": pid, "duration_seconds": "1.0"},
            files={"audio": ("r.webm", io.BytesIO(b"tiny"), "audio/webm")},
        )
        assert r.status_code in (400, 422)

    @patch("app.stt_service.STTService._transcribe_once", new_callable=AsyncMock,
           return_value=FAKE_STT_RESULT)
    def test_analyze_reading_success(self, mock_stt, client):
        passages = client.get("/api/passages?language=hi").json().get("passages", [])
        if not passages:
            pytest.skip("No Hindi passages")
        pid = passages[0]["id"]

        r = client.post(
            "/api/analyze-reading",
            data={"passage_id": pid, "duration_seconds": "3.0", "student_id": "student-1"},
            files={"audio": ("rec.webm", io.BytesIO(FAKE_AUDIO), "audio/webm")},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "session_id" in data
        assert "metrics" in data
        assert "structured_errors" in data

    @patch("app.stt_service.STTService._transcribe_once", new_callable=AsyncMock,
           return_value=FAKE_STT_RESULT)
    def test_analyze_reading_has_no_audio_retained_header(self, mock_stt, client):
        passages = client.get("/api/passages?language=hi").json().get("passages", [])
        if not passages:
            pytest.skip("No Hindi passages")
        pid = passages[0]["id"]
        r = client.post(
            "/api/analyze-reading",
            data={"passage_id": pid, "duration_seconds": "3.0"},
            files={"audio": ("rec.webm", io.BytesIO(FAKE_AUDIO), "audio/webm")},
        )
        assert r.headers.get("x-audio-retained") == "false"


class TestRemediationGenerateEndpoint:
    @patch("app.remediation.generate_remediation_story_gemini", new_callable=AsyncMock,
           return_value=FAKE_STORY)
    def test_generate_returns_story(self, mock_gemini, client):
        r = client.post("/api/rank-and-generate-remediation", json={
            "grade_level": 4,
            "language": "hi",
            "student_name": "Aarav",
            "theme": "space",
            "override_target_words": ["प्रकाश", "आकाश"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "remediation_passage" in data
        assert "target_words" in data
