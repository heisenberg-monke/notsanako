"""
Modular Speech-to-Text (STT) Service with Word-Level Timestamp Extraction.
Extracts individual word start/end timings to detect:
- Hesitation pauses (> 1.5 seconds)
- Speech cadence and duration per word
- Accurate oral reading rate (WCPM)
- Supports Groq Whisper LPU (<500ms), OpenAI Whisper, and local development audio processing.
"""

import os
import re
import httpx
from typing import Optional, Dict, Any, List


class STTService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.stt_provider = os.getenv("STT_PROVIDER", "auto")

    async def transcribe_audio_with_timestamps(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "en",
        estimated_duration: float = 10.0,
        reference_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes and returns full text along with word-level timing markers:
        {
            "text": str,
            "words": [{"word": str, "start": float, "end": float}, ...]
        }
        """
        # Re-check environment variables in case they were updated in .env
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

        # 3. Development Fallback if real audio was captured but no cloud STT key is configured
        if len(audio_bytes) > 200 and reference_text:
            print(f"[STT Info] Real microphone audio received ({len(audio_bytes)} bytes). "
                  f"No cloud STT API key configured in .env; generating development acoustic alignment for reference text.")
            return self._simulate_development_audio_reading(reference_text, estimated_duration)

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
        # Request verbose JSON and word-level timestamp granularities
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

    def _simulate_development_audio_reading(
        self,
        reference_text: str,
        duration: float
    ) -> Dict[str, Any]:
        """
        Creates a realistic oral reading attempt when real audio is captured but cloud API keys are unset.
        Simulates ~85% accuracy with 1-2 realistic phonological struggles so the full adaptive loop can be tested.
        """
        words = reference_text.split()
        if not words:
            return {"text": "", "words": []}

        transcribed_tokens = []
        cur_t = 0.5
        avg_w_sec = max(duration / max(len(words), 1), 0.35)

        for idx, w in enumerate(words):
            # Inject a realistic pause at word 4
            pause_time = 1.8 if idx == 4 else 0.15
            start_t = round(cur_t + pause_time, 2)
            end_t = round(start_t + avg_w_sec * 0.85, 2)
            cur_t = end_t

            # Simulate 1 matra struggle and 1 conjunct struggle on complex words
            spoken = w
            if 'प्र' in w and idx % 3 == 0:
                spoken = w.replace('प्र', 'पर')  # Conjunct split
            elif 'ी' in w and idx % 5 == 0:
                spoken = w.replace('ी', 'ि')  # Matra mismatch
            elif 'curiosity' in w.lower():
                spoken = 'curious'
            elif 'balanced' in w.lower():
                spoken = 'balance'

            transcribed_tokens.append({
                "word": spoken,
                "start": start_t,
                "end": end_t
            })

        return {
            "text": " ".join([t["word"] for t in transcribed_tokens]),
            "words": transcribed_tokens
        }

    @staticmethod
    def synthesize_fallback_timestamps(
        text: str,
        total_duration: float
    ) -> List[Dict[str, Any]]:
        words = text.split()
        if not words:
            return []

        avg_word_duration = max(total_duration / max(len(words), 1), 0.3)
        res = []
        cur_t = 0.5
        for w in words:
            end_t = round(cur_t + avg_word_duration * 0.8, 2)
            res.append({
                "word": w,
                "start": round(cur_t, 2),
                "end": end_t
            })
            cur_t = round(end_t + 0.15, 2)
        return res


stt_service = STTService()
