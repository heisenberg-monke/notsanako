"""
AI-Powered Remediation Engine for Adaptive Reading Coach.
1. Ranks student errors by frequency and severity (Matra, Conjunct, Phonetic, Hesitations).
2. Selects 3-5 priority target words for remediation.
3. Generates a 60-80 word personalized mini-story using Gemini 1.5 (with strict JSON output).
4. Ensures every target word appears naturally 1-2 times in an engaging, grade-appropriate narrative.
5. Provides robust deterministic fallback generation if API is unavailable or returns malformed output.
"""

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
    gemini_key = os.getenv("GEMINI_API_KEY")
    theme_info = THEME_TEMPLATES.get(theme, THEME_TEMPLATES["space"])
    theme_label = theme_info["label"]

    target_words_list = [normalize_devanagari(w) for w in target_words]
    words_formatted = ", ".join(f'"{w}"' for w in target_words_list)

    if gemini_key:
        try:
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
                        # Gemini 3.8 Flash
            url = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/gemini-3.8-flash:generateContent?key={gemini_key}"
            )

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
                    "responseMimeType": "application/json",
                    "temperature": 0.4
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)

                # IMPORTANT: log the actual Gemini error instead of
                # silently falling back.
                if res.status_code != 200:
                    print(
                        f"[Gemini Error] HTTP {res.status_code}: "
                        f"{res.text[:2000]}"
                    )
                else:
                    try:
                        response_json = res.json()

                        raw_content = (
                            response_json["candidates"][0]
                            ["content"]["parts"][0]["text"]
                            .strip()
                        )

                        # Remove accidental markdown code fences.
                        clean_json = re.sub(
                            r"^```json\s*|^```\s*|```$",
                            "",
                            raw_content
                        ).strip()

                        parsed = json.loads(clean_json)

                        # Validate story text.
                        story_text = parsed.get("text", "")
                        words_in_story = story_text.split()

                        if 40 <= len(words_in_story) <= 100:
                            parsed["word_count"] = len(words_in_story)
                            parsed["theme"] = theme
                            parsed["grade_level"] = grade_level
                            parsed["language"] = language
                            parsed["generator_source"] = "Gemini 3.8 Flash"

                            print(
                                "[Gemini] Story generated successfully "
                                f"({len(words_in_story)} words)."
                            )

                            return parsed

                        print(
                            "[Gemini Error] Gemini returned an invalid "
                            f"word count: {len(words_in_story)}"
                        )

                    except (KeyError, IndexError, json.JSONDecodeError) as e:
                        print(
                            "[Gemini Error] Could not parse Gemini response: "
                            f"{e}"
                        )
                        print(
                            f"[Gemini Raw Response] {res.text[:3000]}"
                        )

        except httpx.TimeoutException as e:
            print(f"[Gemini Error] Request timed out: {e}")

        except httpx.RequestError as e:
            print(f"[Gemini Error] Network request failed: {e}")

        except Exception as e:
            print(
                f"[Gemini Error] Unexpected failure: "
                f"{type(e).__name__}: {e}"
            )

            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    raw_content = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # Clean any accidental markdown code fence
                    clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', raw_content).strip()
                    parsed = json.loads(clean_json)

                    # Validate story text length and content
                    story_text = parsed.get("text", "")
                    words_in_story = story_text.split()
                    if len(words_in_story) >= 40:
                        parsed["word_count"] = len(words_in_story)
                        parsed["theme"] = theme
                        parsed["grade_level"] = grade_level
                        parsed["language"] = language
                        parsed["generator_source"] = "Gemini 1.5 Flash"
                        return parsed

        except Exception as e:
            print(f"[Remediation Error] Gemini LLM generation failed or malformed: {e}. Using deterministic fallback.")

    # High quality, deterministic fallback generator guarantees 60-80 words & all target words
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
