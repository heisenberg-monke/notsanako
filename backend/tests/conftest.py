"""
Shared pytest fixtures for Adaptive Reading Coach test suite.
All tests use an in-memory SQLite database — never touch the production DB.
External APIs (Groq, Gemini, Resend) are never called from tests.
"""
import os
import pytest
from dotenv import load_dotenv

# Load .env for any non-API-key settings (e.g. LOG_LEVEL)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Force in-memory SQLite and stub API keys before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["RESEND_API_KEY"] = ""           # disable email in tests
os.environ["TELEMETRY_SALT"] = "test-salt"

from app.db import Base, engine, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create ORM tables in the in-memory test DB once per session."""
    Base.metadata.create_all(bind=engine)
    init_db()   # seeds demo teacher/classroom/students
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_test_db):
    """Synchronous FastAPI TestClient (wraps lifespan correctly)."""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_PASSAGE_HI = "आकाश में तारे चमकते हैं। बच्चे खेलते हैं।"
SAMPLE_PASSAGE_EN = "The sky is full of stars. Children play in the park."

SAMPLE_WORDS_HI = [
    {"word": "आकाश", "start": 0.0, "end": 0.5},
    {"word": "में",   "start": 0.6, "end": 0.8},
    {"word": "तारे",  "start": 0.9, "end": 1.2},
    {"word": "चमकते","start": 1.3, "end": 1.7},
    {"word": "हैं",   "start": 1.8, "end": 2.0},
]

SAMPLE_ERRORS = [
    {
        "word": "प्रकाश", "spoken_word": "पकाश", "error_type": "CONJUNCT",
        "target_pattern": "प्र", "linguistic_detail": "Dropped conjunct prefix",
        "pedagogical_remedy": "Practise pr- words",
        "pause_before": 0.0, "in_stumble_cluster": False,
    },
    {
        "word": "किताब", "spoken_word": "कीताब", "error_type": "MATRA",
        "target_pattern": "ि vs ी", "linguistic_detail": "Short/long i confusion",
        "pedagogical_remedy": "Drill hrasva-i vs deergha-ee",
        "pause_before": 0.0, "in_stumble_cluster": True,
    },
    {
        "word": "तारा", "spoken_word": "टारा", "error_type": "PHONETIC",
        "target_pattern": "त vs ट", "linguistic_detail": "Dental/retroflex mix",
        "pedagogical_remedy": "Mirror/tongue-tip drill",
        "pause_before": 2.0, "in_stumble_cluster": False,
    },
]

# Minimal valid WebM header + silence padding (>2 KB so size check passes)
# Byte-variance is high enough because of the header bytes (not all 0x80)
FAKE_AUDIO_BYTES = b"\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x1f" + bytes(
    (i % 256) for i in range(3000)
)
