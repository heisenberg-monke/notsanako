"""
Modular Speech-to-Text (STT) Service with Word-Level Timestamp Extraction.
Extracts individual word start/end timings to detect:
- Hesitation pauses (> 1.5 seconds)
- Speech cadence and duration per word
- Accurate oral reading rate (WCPM)

Architecture Rule:
- Relies strictly on authoritative backend STT (Groq Whisper or OpenAI Whisper).
- Does NOT silently simulate reading when API keys are missing.
- Raises explicit configuration errors when STT credentials are unconfigured.
"""

import os
import httpx
from typing import Optional, Dict, Any, List


class STTConfigurationError(Exception):
    """Raised when no valid speech-to-text provider API key is configured."""
    pass


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
        estimated_duration: float = 10.0
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes using configured backend STT providers.
        Returns:
        {
            "text": str,
            "words": [{"word": str, "start": float, "end": float}, ...]
        }
        Raises STTConfigurationError if neither Groq nor OpenAI API key is set.
        """
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        # 1. Try Groq Whisper with word-level timestamp granularity
        if self.groq_api_key and (self.stt_provider in ("auto", "groq")):
            try:
                res = await self._transcribe_groq_verbose(audio_bytes, filename, language)
                if res.get("text"):
                    return res
            except Exception as e:
                print(f"[STT Error] Groq STT with timestamps failed: {e}. Falling back...")

        # 2. Try OpenAI Whisper with verbose_json
        if self.openai_api_key and (self.stt_provider in ("auto", "openai")):
            try:
                res = await self._transcribe_openai_verbose(audio_bytes, filename, language)
                if res.get("text"):
                    return res
            except Exception as e:
                print(f"[STT Error] OpenAI STT failed: {e}. Falling back...")

        # 3. Explicit error: NO silent simulation when keys are missing
        if not self.groq_api_key and not self.openai_api_key:
            raise STTConfigurationError(
                "STT_NOT_CONFIGURED: No Speech-to-Text API key found in backend/.env. "
                "The Adaptive Reading Coach requires backend STT (not browser SpeechRecognition). "
                "Please set GROQ_API_KEY (recommended: https://console.groq.com) or OPENAI_API_KEY in backend/.env to transcribe audio."
            )

        return {
            "text": "",
            "words": []
        }

    async def _transcribe_groq_verbose(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str
    ) -> Dict[str, Any]:
        """Calls Groq Whisper API requesting verbose_json with word-level timestamps."""
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.groq_api_key}"}

        files = {
            "file": (filename, audio_bytes, "audio/wav" if filename.endswith(".wav") else "audio/webm")
        }
        data = [
            ("model", "whisper-large-v3"),
            ("response_format", "verbose_json"),
            ("language", language),
            ("timestamp_granularities[]", "word")
        ]

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            data_json = resp.json()

            text = data_json.get("text", "").strip()
            raw_words = data_json.get("words", [])

            formatted_words = []
            for item in raw_words:
                formatted_words.append({
                    "word": item.get("word", "").strip(),
                    "start": round(float(item.get("start", 0.0)), 2),
                    "end": round(float(item.get("end", 0.0)), 2)
                })

            return {
                "text": text,
                "words": formatted_words
            }

    async def _transcribe_openai_verbose(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str
    ) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}

        files = {
            "file": (filename, audio_bytes, "audio/wav" if filename.endswith(".wav") else "audio/webm")
        }
        data = [
            ("model", "whisper-1"),
            ("response_format", "verbose_json"),
            ("language", language),
            ("timestamp_granularities[]", "word")
        ]

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            data_json = resp.json()

            text = data_json.get("text", "").strip()
            raw_words = data_json.get("words", [])

            formatted_words = []
            for item in raw_words:
                formatted_words.append({
                    "word": item.get("word", "").strip(),
                    "start": round(float(item.get("start", 0.0)), 2),
                    "end": round(float(item.get("end", 0.0)), 2)
                })

            return {
                "text": text,
                "words": formatted_words
            }


stt_service = STTService()
