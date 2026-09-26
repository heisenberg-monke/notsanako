"""
Modular Speech-to-Text (STT) Service with Authoritative Backend Transcription.
- Real-time logging of STT request, audio size, provider, HTTP status, and error body.
- Does NOT swallow provider errors: raises STTProviderError, STTTimeoutError, STTNotConfiguredError.
- Does NOT allow empty transcripts: raises STTEmptyTranscriptionError.
- Sub-second word-level timestamp boundaries using Groq Whisper LPU or OpenAI Whisper.
- Transport: pure httpx.AsyncClient (no sync transport) — compatible with FastAPI / asyncio event loop.
"""

import os
import time
import httpx
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Timeout: 45 s connect + 45 s read.
# Groq LPU is fast but file upload can take a few seconds on slow links;
# OpenAI Whisper queues can add latency — 45 s gives a comfortable margin.
# ---------------------------------------------------------------------------
_STT_TIMEOUT = httpx.Timeout(connect=10.0, read=45.0, write=45.0, pool=5.0)


class STTNotConfiguredError(Exception):
    """Raised when no valid speech-to-text API key is found in environment."""
    def __init__(self):
        super().__init__(
            "STT_API_KEY_MISSING: STT API key is not configured. "
            "Please set GROQ_API_KEY (recommended: https://console.groq.com) "
            "or OPENAI_API_KEY in backend/.env to transcribe audio."
        )


class STTProviderError(Exception):
    """Raised when the upstream STT provider (Groq/OpenAI) fails with an HTTP error."""
    def __init__(self, provider: str, status_code: int, message: str, raw_body: str = ""):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        self.raw_body = raw_body
        super().__init__(f"[{provider} STT Error {status_code}] {message}")


class STTTimeoutError(Exception):
    """Raised when upstream STT provider times out."""
    def __init__(self, provider: str, timeout_seconds: float):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"[{provider} STT Timeout] Transcription timed out after {timeout_seconds} s. "
            "Please check your network connection."
        )


class STTEmptyTranscriptionError(Exception):
    """Raised when STT completes with HTTP 200 but produces no recognized words."""
    def __init__(self, audio_size_kb: float):
        super().__init__(
            f"Transcription failed: No speech could be recognized from the recording "
            f"({audio_size_kb} KB). Please speak clearly into the microphone and check "
            "your input volume."
        )


class STTService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.stt_provider = os.getenv("STT_PROVIDER", "auto")

    async def transcribe_audio_with_timestamps(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "en",
        estimated_duration: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes using configured backend STT providers.

        Returns:
            {
                "text": str,
                "words": [{"word": str, "start": float, "end": float}, ...]
            }

        Raises explicit exceptions on missing keys, provider failures,
        timeouts, or empty transcripts — never falls back silently.
        """
        # Re-read env at call time so a hot-reloaded .env is picked up
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        audio_kb = round(len(audio_bytes) / 1024, 2)

        if not self.groq_api_key and not self.openai_api_key:
            print(f"[STT Error] Attempted transcription without API key ({audio_kb} KB received).")
            raise STTNotConfiguredError()

        if self.groq_api_key and self.stt_provider in ("auto", "groq"):
            return await self._transcribe_groq_verbose(audio_bytes, filename, language, audio_kb)

        if self.openai_api_key and self.stt_provider in ("auto", "openai"):
            return await self._transcribe_openai_verbose(audio_bytes, filename, language, audio_kb)

        raise STTNotConfiguredError()

    # ------------------------------------------------------------------
    # Groq Whisper Large-v3
    # ------------------------------------------------------------------
    async def _transcribe_groq_verbose(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str,
        audio_kb: float,
    ) -> Dict[str, Any]:
        """Calls Groq Whisper API with verbose_json and word-level timestamps."""
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.groq_api_key}"}

        # Determine MIME type from extension
        mime = "audio/wav" if filename.lower().endswith(".wav") else "audio/webm"

        # IMPORTANT: Do NOT split into files= + data= simultaneously.
        # httpx.AsyncClient uses the sync MultipartStream code path when both
        # are provided, raising "Attempted to send a sync request with an
        # AsyncClient instance."  Put every field — text and file alike — into
        # a single `files` list so the fully-async encoder is used throughout.
        multipart = [
            ("model",                    (None, "whisper-large-v3")),
            ("response_format",          (None, "verbose_json")),
            ("language",                 (None, language)),
            ("timestamp_granularities[]",(None, "word")),
            ("file",                     (filename, audio_bytes, mime)),
        ]

        t0 = time.time()
        print(
            f"[STT Request Started] Provider=Groq | File={filename} | "
            f"Size={audio_kb} KB | Lang={language}"
        )

        try:
            # Pure async client — no transport= argument, no sync transport.
            async with httpx.AsyncClient(timeout=_STT_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, files=multipart)

            duration = round(time.time() - t0, 2)
            print(
                f"[STT Response Received] Provider=Groq | "
                f"Status={resp.status_code} | Duration={duration}s"
            )

            if resp.status_code != 200:
                raw_err = resp.text
                print(f"[STT Failure] Groq returned HTTP {resp.status_code}: {raw_err}")
                try:
                    err_msg = resp.json().get("error", {}).get("message") or raw_err
                except Exception:
                    err_msg = raw_err
                raise STTProviderError("Groq", resp.status_code, err_msg, raw_body=raw_err)

            payload = resp.json()
            text = payload.get("text", "").strip()
            raw_words = payload.get("words", [])

            if not text:
                print(f"[STT Empty Error] Groq returned 0 words for {audio_kb} KB audio.")
                raise STTEmptyTranscriptionError(audio_kb)

            words = [
                {
                    "word": w.get("word", "").strip(),
                    "start": round(float(w.get("start", 0.0)), 2),
                    "end": round(float(w.get("end", 0.0)), 2),
                }
                for w in raw_words
            ]

            print(
                f'[STT Completed] Groq → {len(words)} words in {duration}s: '
                f'"{text[:60]}{"..." if len(text) > 60 else ""}"'
            )
            return {"text": text, "words": words}

        except httpx.TimeoutException:
            print(f"[STT Timeout Error] Groq timed out after {_STT_TIMEOUT.read}s.")
            raise STTTimeoutError("Groq", float(_STT_TIMEOUT.read or 45.0))
        except httpx.RequestError as req_err:
            print(f"[STT Network Error] Groq: {req_err}")
            raise STTProviderError(
                "Groq", 503,
                f"Network connection to Groq STT failed: {req_err}"
            )

    # ------------------------------------------------------------------
    # OpenAI Whisper-1
    # ------------------------------------------------------------------
    async def _transcribe_openai_verbose(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str,
        audio_kb: float,
    ) -> Dict[str, Any]:
        """Calls OpenAI Whisper API with verbose_json and word-level timestamps."""
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}

        mime = "audio/wav" if filename.lower().endswith(".wav") else "audio/webm"

        # Same fix as Groq path: merge all fields into a single `files` list
        # so httpx uses the fully-async multipart encoder end-to-end.
        multipart = [
            ("model",                    (None, "whisper-1")),
            ("response_format",          (None, "verbose_json")),
            ("language",                 (None, language)),
            ("timestamp_granularities[]",(None, "word")),
            ("file",                     (filename, audio_bytes, mime)),
        ]

        t0 = time.time()
        print(
            f"[STT Request Started] Provider=OpenAI | File={filename} | "
            f"Size={audio_kb} KB | Lang={language}"
        )

        try:
            # Pure async client — no transport= argument, no sync transport.
            async with httpx.AsyncClient(timeout=_STT_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, files=multipart)

            duration = round(time.time() - t0, 2)
            print(
                f"[STT Response Received] Provider=OpenAI | "
                f"Status={resp.status_code} | Duration={duration}s"
            )

            if resp.status_code != 200:
                raw_err = resp.text
                print(f"[STT Failure] OpenAI returned HTTP {resp.status_code}: {raw_err}")
                try:
                    err_msg = resp.json().get("error", {}).get("message") or raw_err
                except Exception:
                    err_msg = raw_err
                raise STTProviderError("OpenAI", resp.status_code, err_msg, raw_body=raw_err)

            payload = resp.json()
            text = payload.get("text", "").strip()
            raw_words = payload.get("words", [])

            if not text:
                print(f"[STT Empty Error] OpenAI returned 0 words for {audio_kb} KB audio.")
                raise STTEmptyTranscriptionError(audio_kb)

            words = [
                {
                    "word": w.get("word", "").strip(),
                    "start": round(float(w.get("start", 0.0)), 2),
                    "end": round(float(w.get("end", 0.0)), 2),
                }
                for w in raw_words
            ]

            print(
                f'[STT Completed] OpenAI → {len(words)} words in {duration}s: '
                f'"{text[:60]}{"..." if len(text) > 60 else ""}"'
            )
            return {"text": text, "words": words}

        except httpx.TimeoutException:
            print(f"[STT Timeout Error] OpenAI timed out after {_STT_TIMEOUT.read}s.")
            raise STTTimeoutError("OpenAI", float(_STT_TIMEOUT.read or 45.0))
        except httpx.RequestError as req_err:
            print(f"[STT Network Error] OpenAI: {req_err}")
            raise STTProviderError(
                "OpenAI", 503,
                f"Network connection to OpenAI STT failed: {req_err}"
            )


stt_service = STTService()
