"""
AI-Powered Remediation Engine for Adaptive Reading Coach.
1. Ranks student errors by frequency and severity (Matra, Conjunct, Phonetic, Hesitations).
2. Selects 3-5 priority target words for remediation.
3. Generates a 60-80 word personalized mini-story using Gemini 1.5 (with strict JSON output).
4. Ensures every target word appears naturally 1-2 times in an engaging, grade-appropriate narrative.
5. Provides robust deterministic fallback generation if API is unavailable or returns malformed output.
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
    Generates a 60-80 word structured mini-story embedding target words using Gemini 1.5.
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
                            fallback_reason = f"{model} returned HTTP {res.status_code}"
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
                fallback_reason = f"OpenAI returned HTTP {response.status_code}"
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
    else:
        fallback_reason = f"{fallback_reason}; OPENAI_API_KEY is not configured"

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        groq_model = os.getenv(
            "GROQ_REMEDIATION_MODEL",
            "openai/gpt-oss-20b",
        )
        groq_payload = {
            "model": groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert children's reading coach. Follow the user's story requirements and return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json=groq_payload,
                )

            if response.status_code != 200:
                fallback_reason = f"Groq returned HTTP {response.status_code}"
                print(
                    f"[Groq Error] HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )
            else:
                response_json = response.json()
                raw_content = response_json["choices"][0]["message"]["content"]
                parsed = json.loads(raw_content)
                story_text = parsed.get("text", "")
                words_in_story = story_text.split()

                if 40 <= len(words_in_story) <= 100:
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
    else:
        fallback_reason = f"{fallback_reason}; GROQ_API_KEY is not configured"

    # High quality, deterministic fallback generator guarantees 60-80 words & all target words
    print(f"[Story Generation] Using deterministic fallback ({fallback_reason}).")
    return build_deterministic_remediation_story(
        target_words=target_words_list,
        grade_level=grade_level,
        language=language,
        student_name=student_name,
        theme=theme
    )


def build_deterministic_remediation_story(
    target_words: List[str],
    grade_level: int = 4,
    language: str = "hi",
    student_name: str = "Aarav",
    theme: str = "space"
) -> Dict[str, Any]:
    """
    Robust fallback that guarantees:
    - 60-80 words
    - Every target word appears 1-2 times
    - Valid structured schema with sentence list and word occurrence map
    """
    theme_info = THEME_TEMPLATES.get(theme, THEME_TEMPLATES["space"])

    if language == "hi":
        w1 = target_words[0] if len(target_words) > 0 else "साहस"
        w2 = target_words[1] if len(target_words) > 1 else "परिश्रम"
        w3 = target_words[2] if len(target_words) > 2 else "बुद्धिमान"
        w4 = target_words[3] if len(target_words) > 3 else "प्रशंसा"
        w5 = target_words[4] if len(target_words) > 4 else w1

        title = f"{student_name} का नया सफर"
        s1 = f"एक सुनहरी सुबह {student_name} ने आसमान की ओर देखा और एक नया सपना संजोया।"
        s2 = f"उन्होंने जाना कि किसी भी मुश्किल काम में {w1} और {w2} सबसे सच्चे साथी होते हैं।"
        s3 = f"जब उन्होंने अपनी नई योजना बनाई, तो एक {w3} बालक की तरह हर बात को गहराई से समझा।"
        s4 = f"गुरुजी ने {student_name} के काम की {w4} की और कहा कि {w1} से हर लक्ष्य प्राप्त होता है।"
        s5 = f"शाम को गाँव के सभी लोगों ने {w5} की सराहना की और मुस्कुराते हुए उनका हौसला बढ़ाया।"

        sentences = [s1, s2, s3, s4, s5]
        full_text = " ".join(sentences)

    else:
        w1 = target_words[0] if len(target_words) > 0 else "curiosity"
        w2 = target_words[1] if len(target_words) > 1 else "balanced"
        w3 = target_words[2] if len(target_words) > 2 else "sparked"
        w4 = target_words[3] if len(target_words) > 3 else "cheerful"
        w5 = target_words[4] if len(target_words) > 4 else w1

        title = f"{student_name}'s Bright Adventure"
        s1 = f"Early one sunny morning, young {student_name} embarked on an inspiring journey across the valley."
        s2 = f"To succeed in this quest, having pure {w1} and a steady mind proved essential."
        s3 = f"Along the breezy trail, walking with a {w2} pace helped overcome every steep hill."
        s4 = f"A kind teacher smiled warmly and noted how this effort {w3} immense hope in everyone."
        s5 = f"Soon, the {w4} companions gathered together to celebrate their shared triumph with great {w5}."

        sentences = [s1, s2, s3, s4, s5]
        full_text = " ".join(sentences)

    # Build target word occurrences map
    occurrences = []
    full_lower = full_text.lower()
    for w in target_words:
        matched_sentences = []
        count = 0
        for s_idx, s in enumerate(sentences):
            if w.lower() in s.lower():
                matched_sentences.append(s_idx)
                count += s.lower().count(w.lower())
        occurrences.append({
            "word": w,
            "occurrences_count": max(1, count),
            "sentence_indices": matched_sentences or [0]
        })

    return {
        "title": title,
        "text": full_text,
        "sentences": sentences,
        "target_word_occurrences": occurrences,
        "word_count": len(full_text.split()),
        "theme": theme,
        "grade_level": grade_level,
        "language": language,
        "generator_source": "Deterministic Template Fallback"
    }


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
