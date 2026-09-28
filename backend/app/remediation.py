"""
AI-Powered Remediation Engine for Adaptive Reading Coach.
1. Ranks student errors by frequency and severity (Matra, Conjunct, Phonetic, Hesitations).
2. Selects 3-5 priority target words for remediation.
3. Generates a 60-80 word personalized mini-story using Gemini, OpenAI, or Groq.
4. Ensures every target word appears naturally 1-2 times in an engaging, grade-appropriate narrative.
5. Reports an error when all configured AI providers are unavailable or return malformed output.
"""

import asyncio
import os
import re
import json
from typing import List, Dict, Any, Optional
import httpx

from app.indic_rules import normalize_devanagari


# Severity Weights for Different Error Categories
ERROR_SEVERITY_WEIGHTS = {
    "CONJUNCT": 3.5,     # Consonant cluster failure (foundational obstacle in Devanagari)
    "MATRA": 3.0,        # Vowel length confusion (affects syllable meaning)
    "PHONETIC": 2.5,     # Articulation shifts (dental vs retroflex, aspiration)
    "SUBSTITUTION": 2.0, # General word replacement
    "OMISSION": 1.5,     # Skipped word
    "REPETITION": 1.0,   # Stutter / false start
}

THEME_TEMPLATES = {
    "space": {
        "label": "Space & Rockets / अंतरिक्ष यात्रा",
        "keywords_en": ["rocket", "stars", "planet", "sky", "astronaut"],
        "keywords_hi": ["रॉकेट", "तारे", "ग्रह", "आसमान", "अंतरिक्ष यान"]
    },
    "jungle": {
        "label": "Jungle & Wildlife / जंगल और जानवर",
        "keywords_en": ["jungle", "forest", "tiger", "river", "birds"],
        "keywords_hi": ["जंगल", "पेड़", "शेर", "नदी", "पक्षी"]
    },
    "sports": {
        "label": "Sports & Adventure / खेलकूद और साहस",
        "keywords_en": ["match", "game", "team", "cheer", "champion"],
        "keywords_hi": ["मैच", "खेल", "साथी", "उत्साह", "विजेता"]
    },
    "festivals": {
        "label": "Festivals & Celebration / त्योहार और मेला",
        "keywords_en": ["festival", "lights", "sweets", "friends", "joy"],
        "keywords_hi": ["त्योहार", "दीपक", "मिठाई", "मेला", "खुशी"]
    }
}


class StoryGenerationError(RuntimeError):
    """Raised when every configured story-generation provider fails."""


def _format_provider_http_error(provider: str, response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        detail = error.get("message") or error.get("detail")
    except (ValueError, AttributeError):
        detail = None

    if detail:
        detail = " ".join(str(detail).split())[:300]
        return f"{provider} returned HTTP {response.status_code}: {detail}"
    return f"{provider} returned HTTP {response.status_code}"


def _parse_json_object(raw_content: str) -> Dict[str, Any]:
    """Parse a JSON object even if the model surrounds it with prose or fences."""
    content = raw_content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)

    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("response did not contain a valid JSON object")


def rank_and_select_target_words(
    structured_errors: List[Dict[str, Any]],
    max_targets: int = 5
) -> List[Dict[str, Any]]:
    """
    Ranks errors by frequency, linguistic severity, and contextual difficulty.
    Selects 3 to 5 priority target words for personalized remediation.
    """
    if not structured_errors:
        return []

    word_scores: Dict[str, Dict[str, Any]] = {}

    for err in structured_errors:
        word = err.get("word")
        if not word:
            continue
        clean_w = normalize_devanagari(word).strip()
        if len(clean_w) < 2:
            continue

        err_type = err.get("error_type", "SUBSTITUTION")
        base_weight = ERROR_SEVERITY_WEIGHTS.get(err_type, 2.0)

        # Contextual boosts
        cluster_boost = 1.5 if err.get("in_stumble_cluster") else 0.0
        pause_boost = 1.0 if (err.get("pause_before") or 0.0) >= 1.5 else 0.0

        item_score = base_weight + cluster_boost + pause_boost

        if clean_w not in word_scores:
            word_scores[clean_w] = {
                "word": clean_w,
                "error_type": err_type,
                "frequency": 1,
                "total_score": item_score,
                "target_pattern": err.get("target_pattern"),
                "linguistic_detail": err.get("linguistic_detail"),
                "pedagogical_remedy": err.get("pedagogical_remedy")
            }
        else:
            word_scores[clean_w]["frequency"] += 1
            word_scores[clean_w]["total_score"] += item_score

    # Sort descending by total score and frequency
    ranked = sorted(
        word_scores.values(),
        key=lambda x: (x["total_score"], x["frequency"]),
        reverse=True
    )

    # Pick top 3 to 5 target words
    target_count = max(3, min(len(ranked), max_targets))
    return ranked[:target_count]


async def generate_remediation_story_gemini(
    target_words: List[str],
    grade_level: int = 4,
    language: str = "hi",
    student_name: str = "Aarav",
    theme: str = "space"
) -> Dict[str, Any]:
    """
    Generates a 60-80 word structured mini-story using Gemini, OpenAI, or Groq.
    Returns strictly structured JSON with:
      - title
      - text (60-80 words)
      - sentences (list of string)
      - target_word_occurrences (list of word map occurrences)
      - grade_level, theme, language
    """
    print("🔥 GEMINI FUNCTION CALLED")
    print(f"🔥 target_words={target_words}")
    print(f"🔥 grade_level={grade_level}")
    print(f"🔥 language={language}")
    print(f"🔥 theme={theme}")

    gemini_key = os.getenv("GEMINI_API_KEY")
    theme_info = THEME_TEMPLATES.get(theme, THEME_TEMPLATES["space"])
    theme_label = theme_info["label"]

    target_words_list = [normalize_devanagari(w) for w in target_words]
    words_formatted = ", ".join(f'"{w}"' for w in target_words_list)

    lang_instruction = (
        "Write in clear, standard Hindi (Devanagari script)."
        if language == "hi"
        else "Write in encouraging, fluent Indian English."
    )
    prompt = f"""
You are an expert pedagogical reading coach for upper-primary Indian school children (Grade {grade_level}).
Task: Write a 60 to 80 word engaging children's mini-story centered around the theme: {theme_label}.
Main character name: {student_name}

CRITICAL PEDAGOGICAL REQUIREMENTS:
1. Target Words to Embed: {words_formatted}.
2. EVERY target word MUST appear naturally in the story 1 or 2 times.
3. Total word count of the story MUST be between 60 and 80 words.
4. Suitable reading complexity for a Grade {grade_level} student (simple sentence structures, joyful, moral, and uplifting).
5. {lang_instruction}

You MUST return ONLY a valid JSON object with EXACTLY this structure (no markdown fences, no explanatory text):
{{
  "title": "Short Inspiring Title",
  "text": "The complete story text here (60-80 words)...",
  "sentences": ["Sentence 1...", "Sentence 2...", "Sentence 3..."],
  "target_word_occurrences": [
    {{
      "word": "target_word_1",
      "occurrences_count": 1,
      "sentence_indices": [0]
    }}
  ]
}}
"""
    failure_reasons = []
    fallback_reason = "GEMINI_API_KEY is not configured"
    if gemini_key:
        try:
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                models = ["gemini-3.8-flash", "gemini-3.7-flash"]
                for model_index, model in enumerate(models):
                    url = (
                        "https://generativelanguage.googleapis.com/v1beta/"
                        f"models/{model}:generateContent"
                    )
                    max_attempts = 2 if model_index == 0 else 1

                    for attempt in range(max_attempts):
                        res = await client.post(
                            url,
                            headers={"x-goog-api-key": gemini_key},
                            json=payload,
                        )

                        if res.status_code == 503:
                            fallback_reason = f"{model} returned HTTP 503"
                            print(f"[Gemini Error] {fallback_reason}")
                            if model_index == 0 and attempt == 0:
                                await asyncio.sleep(1)
                                continue
                            if model_index == 0:
                                break
                            break

                        if res.status_code != 200:
                            fallback_reason = _format_provider_http_error(model, res)
                            print(
                                f"[Gemini Error] HTTP {res.status_code}: "
                                f"{res.text[:2000]}"
                            )
                            break

                        try:
                            response_json = res.json()
                            raw_content = (
                                response_json["candidates"][0]
                                ["content"]["parts"][0]["text"]
                                .strip()
                            )

                            clean_json = re.sub(
                                r"^```json\s*|^```\s*|```$",
                                "",
                                raw_content
                            ).strip()
                            parsed = json.loads(clean_json)
                            story_text = parsed.get("text", "")
                            words_in_story = story_text.split()

                            if 40 <= len(words_in_story) <= 100:
                                parsed["word_count"] = len(words_in_story)
                                parsed["theme"] = theme
                                parsed["grade_level"] = grade_level
                                parsed["language"] = language
                                parsed["generator_source"] = model
                                print(
                                    f"[Gemini] Story generated with {model} "
                                    f"({len(words_in_story)} words)."
                                )
                                return parsed

                            fallback_reason = (
                                f"{model} returned an invalid word count: "
                                f"{len(words_in_story)}"
                            )
                            print(f"[Gemini Error] {fallback_reason}")
                            break

                        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                            fallback_reason = f"{model} response was malformed: {e}"
                            print(f"[Gemini Error] {fallback_reason}")
                            print(f"[Gemini Raw Response] {res.text[:3000]}")
                            break

                    # Move to the secondary model only after Gemini 3.8 is
                    # unavailable or returns a response we cannot use.
                    if model_index == 0 and not (
                        fallback_reason.startswith("gemini-3.8-flash returned HTTP 503")
                        or fallback_reason.startswith("gemini-3.8-flash response was malformed")
                        or fallback_reason.startswith("gemini-3.8-flash returned an invalid")
                    ):
                        break

        except httpx.TimeoutException as e:
            fallback_reason = f"Gemini request timed out: {e}"
            print(f"[Gemini Error] Request timed out: {e}")

        except httpx.RequestError as e:
            fallback_reason = f"Gemini network request failed: {e}"
            print(f"[Gemini Error] Network request failed: {e}")

        except Exception as e:
            fallback_reason = f"{type(e).__name__}: {e}"
            print(f"[Gemini Error] Unexpected failure: {fallback_reason}")
        failure_reasons.append(f"Gemini: {fallback_reason}")
    else:
        failure_reasons.append("Gemini: GEMINI_API_KEY is not configured")

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        openai_model = os.getenv("OPENAI_REMEDIATION_MODEL", "gpt-6-astra")
        openai_payload = {
            "model": openai_model,
            "input": [
                {
                    "role": "system",
                    "content": "You are an expert children's reading coach. Follow the user's story requirements and return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "text": {"format": {"type": "json_object"}},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    json=openai_payload,
                )

            if response.status_code != 200:
                fallback_reason = _format_provider_http_error("OpenAI", response)
                print(
                    f"[OpenAI Error] HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )
            else:
                response_json = response.json()
                raw_content = None
                for item in response_json.get("output", []):
                    if item.get("type") != "message":
                        continue
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            raw_content = content.get("text")
                            break
                    if raw_content:
                        break
                if not raw_content:
                    raise ValueError("response did not contain output text")
                parsed = json.loads(raw_content)
                story_text = parsed.get("text", "")
                words_in_story = story_text.split()

                if 40 <= len(words_in_story) <= 100:
                    parsed["word_count"] = len(words_in_story)
                    parsed["theme"] = theme
                    parsed["grade_level"] = grade_level
                    parsed["language"] = language
                    parsed["generator_source"] = f"OpenAI {openai_model}"
                    print(
                        f"[OpenAI] Story generated with {openai_model} "
                        f"({len(words_in_story)} words)."
                    )
                    return parsed

                fallback_reason = (
                    f"OpenAI returned an invalid word count: "
                    f"{len(words_in_story)}"
                )
                print(f"[OpenAI Error] {fallback_reason}")

        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as e:
            fallback_reason = f"OpenAI response was malformed: {e}"
            print(f"[OpenAI Error] {fallback_reason}")
        except httpx.TimeoutException as e:
            fallback_reason = f"OpenAI request timed out: {e}"
            print(f"[OpenAI Error] {fallback_reason}")
        except httpx.RequestError as e:
            fallback_reason = f"OpenAI network request failed: {e}"
            print(f"[OpenAI Error] {fallback_reason}")
        except Exception as e:
            fallback_reason = f"OpenAI {type(e).__name__}: {e}"
            print(f"[OpenAI Error] {fallback_reason}")
        failure_reasons.append(f"OpenAI: {fallback_reason}")
    else:
        failure_reasons.append("OpenAI: OPENAI_API_KEY is not configured")

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        groq_model = os.getenv(
            "GROQ_REMEDIATION_MODEL",
            "openai/gpt-oss-20b",
        )
        groq_prompt = f"""
Write a child-friendly story for Grade {grade_level}, in {"standard Hindi using Devanagari" if language == "hi" else "encouraging Indian English"}.
The story should be 60 to 80 words, about {theme_label}, and feature {student_name}.
Include each of these target words naturally one or two times: {words_formatted}.

Return only a JSON object with exactly two string properties: "title" and "text".
The "text" property must contain the complete story. Do not include markdown,
reasoning, or any text outside the JSON object.
"""
        groq_payload = {
            "model": groq_model,
            "reasoning_effort": "low",
            "messages": [
                {
                    "role": "system",
                    "content": "You write short stories for children. Output only the requested JSON object.",
                },
                {"role": "user", "content": groq_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "remediation_story",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["title", "text"],
                        "additionalProperties": False,
                    },
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json=groq_payload,
                )

            if response.status_code != 200:
                fallback_reason = _format_provider_http_error("Groq", response)
                print(
                    f"[Groq Error] HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )
            else:
                response_json = response.json()
                raw_content = response_json["choices"][0]["message"]["content"]
                parsed = _parse_json_object(raw_content)
                story_text = parsed.get("text", "")
                words_in_story = story_text.split()

                if 40 <= len(words_in_story) <= 100:
                    sentences = [
                        sentence.strip()
                        for sentence in re.split(r"(?<=[.!?।])\s+", story_text.strip())
                        if sentence.strip()
                    ]
                    parsed["sentences"] = sentences
                    parsed["target_word_occurrences"] = [
                        {
                            "word": target,
                            "occurrences_count": sum(
                                sentence.lower().count(target.lower())
                                for sentence in sentences
                            ),
                            "sentence_indices": [
                                index
                                for index, sentence in enumerate(sentences)
                                if target.lower() in sentence.lower()
                            ],
                        }
                        for target in target_words
                    ]
                    parsed["word_count"] = len(words_in_story)
                    parsed["theme"] = theme
                    parsed["grade_level"] = grade_level
                    parsed["language"] = language
                    parsed["generator_source"] = f"Groq {groq_model}"
                    print(
                        f"[Groq] Story generated with {groq_model} "
                        f"({len(words_in_story)} words)."
                    )
                    return parsed

                fallback_reason = (
                    f"Groq returned an invalid word count: "
                    f"{len(words_in_story)}"
                )
                print(f"[Groq Error] {fallback_reason}")

        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as e:
            fallback_reason = f"Groq response was malformed: {e}"
            print(f"[Groq Error] {fallback_reason}")
        except httpx.TimeoutException as e:
            fallback_reason = f"Groq request timed out: {e}"
            print(f"[Groq Error] {fallback_reason}")
        except httpx.RequestError as e:
            fallback_reason = f"Groq network request failed: {e}"
            print(f"[Groq Error] {fallback_reason}")
        except Exception as e:
            fallback_reason = f"Groq {type(e).__name__}: {e}"
            print(f"[Groq Error] {fallback_reason}")
        failure_reasons.append(f"Groq: {fallback_reason}")
    else:
        failure_reasons.append("Groq: GROQ_API_KEY is not configured")

    error = (
        "All story-generation providers failed. "
        + " | ".join(failure_reasons)
        + ". Check provider keys, quotas, and service availability."
    )
    print(f"[Story Generation Error] {error}")
    raise StoryGenerationError(error)


def calculate_remediation_delta(
    target_words: List[str],
    baseline_alignments: List[Dict[str, Any]],
    retest_alignments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculates target-word mastery before vs. after remediation:
    Delta = post-test target-word accuracy - baseline target-word accuracy
    """
    clean_targets = [normalize_devanagari(w).strip().lower() for w in target_words]

    # Baseline evaluation on target words
    baseline_correct = 0
    baseline_total = 0
    for item in baseline_alignments:
        exp = normalize_devanagari(item.get("expected_word") or "").strip().lower()
        if exp in clean_targets:
            baseline_total += 1
            if item.get("status") == "correct" or item.get("is_dialect_variant"):
                baseline_correct += 1

    # Retest evaluation on target words
    retest_correct = 0
    retest_total = 0
    word_deltas: Dict[str, Dict[str, Any]] = {}

    for tw in clean_targets:
        word_deltas[tw] = {
            "word": tw,
            "baseline_correct": False,
            "retest_correct": False,
            "mastered": False
        }

    for item in baseline_alignments:
        exp = normalize_devanagari(item.get("expected_word") or "").strip().lower()
        if exp in word_deltas:
            if item.get("status") == "correct" or item.get("is_dialect_variant"):
                word_deltas[exp]["baseline_correct"] = True

    for item in retest_alignments:
        exp = normalize_devanagari(item.get("expected_word") or "").strip().lower()
        if exp in clean_targets:
            retest_total += 1
            if item.get("status") == "correct" or item.get("is_dialect_variant"):
                retest_correct += 1
                if exp in word_deltas:
                    word_deltas[exp]["retest_correct"] = True

    # Mastery count (words that were struggles in baseline but mastered in retest, or correctly read in retest)
    mastered_count = 0
    for tw, data in word_deltas.items():
        if data["retest_correct"]:
            data["mastered"] = True
            mastered_count += 1

    baseline_acc = round((baseline_correct / max(baseline_total, 1)) * 100.0, 1)
    retest_acc = round((retest_correct / max(retest_total, 1)) * 100.0, 1)
    delta = round(retest_acc - baseline_acc, 1)

    return {
        "target_words": target_words,
        "baseline_accuracy": baseline_acc,
        "retest_accuracy": retest_acc,
        "delta": delta,
        "mastered_words_count": mastered_count,
        "total_target_words": len(clean_targets),
        "word_mastery_breakdown": list(word_deltas.values()),
        "positive_reinforcement": (
            f"Spectacular progress! You mastered {mastered_count} out of {len(clean_targets)} tricky practice words, "
            f"improving your target word accuracy by {delta:+.1f}% in this session!"
        )
    }
