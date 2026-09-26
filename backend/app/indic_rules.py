"""
Indic Language Linguistic Rules and Diagnostic Engine.
Specifically tailored for Devanagari (Hindi, Marathi) and Indian English phonology.

Classifies reading struggles into:
- MATRA: Vowel length (hrasva vs deergha, e.g. इ/ई, उ/ऊ) or diacritic mismatch
- CONJUNCT: Sanyuktakshar / consonant cluster issues (e.g. प्र, क्ष, त्र, ज्ञ, स्त)
- PHONETIC: Dental vs Retroflex (त/ट, द/ड), Aspirated vs Unaspirated (क/ख, प/फ), Sibilants (स/श/ष)
- DIALECT_EQUIVALENT: Regional pronunciation variations (e.g. /v/ <-> /b/, /s/ <-> /sh/)
  that should NOT unfairly penalize the student.
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple


# Devanagari Unicode Definitions
DEV_VIRAMA = '\u094D'  # ् (Halant / Virama)
DEV_NUKTA = '\u093C'   # ़

# Dependent Vowel Signs (Matras)
MATRAS = {
    '\u093E': 'aa (ा)',
    '\u093F': 'hrasva_i (ि)',
    '\u0940': 'deergha_ee (ी)',
    '\u0941': 'hrasva_u (ु)',
    '\u0942': 'deergha_oo (ू)',
    '\u0943': 'ri (ृ)',
    '\u0947': 'e (े)',
    '\u0948': 'ai (ै)',
    '\u094B': 'o (ो)',
    '\u094C': 'au (ौ)',
    '\u0902': 'anusvara (ं)',
    '\u0901': 'chandrabindu (ँ)',
    '\u0903': 'visarga (ः)',
}

# Vowel pairs commonly confused in foundational reading
MATRA_PAIRS = [
    ('\u093F', '\u0940', 'इ vs ई (Short "i" vs Long "ee")'),
    ('\u0941', '\u0942', 'उ vs ऊ (Short "u" vs Long "oo")'),
    ('\u0947', '\u0948', 'ए vs ऐ (Single vs Double Matra)'),
    ('\u094B', '\u094C', 'ओ vs औ (Single vs Double Kanā-Matra)'),
    ('', '\u093E', 'अ vs आ (Schwa vs Long Aa)'),
]

# Common Conjunct Ligatures and patterns
SPECIAL_CONJUNCTS = {
    'क्ष': 'k-sh (क् + ष)',
    'त्र': 't-r (त् + र)',
    'ज्ञ': 'j-ny (ज् + ञ)',
    'श्र': 'sh-r (श् + र)',
    'द्ध': 'd-dh (द् + ध)',
    'त्त': 't-t (त् + त)',
    'ष्ट': 'sh-t (ष् + ट)',
    'स्त': 's-t (स् + त)',
    'प्र': 'p-r (प् + र)',
    'क्र': 'k-r (क् + र)',
    'ट्र': 't-r (ट् + र)',
    'ड्र': 'd-r (ड् + र)',
    'द्र': 'd-r (द् + र)',
    'ब्र': 'b-r (ब् + र)',
    'ग्र': 'g-r (ग् + र)',
    'श्व': 'sh-v (श् + व)',
}

# Phonetic Confusion Groups (Dental vs Retroflex, Aspiration, Sibilants)
PHONETIC_PAIRS = [
    # Dental vs Retroflex
    ({'त', 'थ'}, {'ट', 'ठ'}, 'Dental (त/थ) vs Retroflex (ट/ठ) mismatch'),
    ({'द', 'ध'}, {'ड', 'ढ'}, 'Dental (द/ध) vs Retroflex (ड/ढ) mismatch'),
    ({'न'}, {'ण'}, 'Dental (न) vs Retroflex (ण)'),
    
    # Aspiration Shifts (Unaspirated vs Aspirated)
    ({'क'}, {'ख'}, 'Unaspirated "क" vs Aspirated "ख"'),
    ({'ग'}, {'घ'}, 'Unaspirated "ग" vs Aspirated "घ"'),
    ({'च'}, {'छ'}, 'Unaspirated "च" vs Aspirated "छ"'),
    ({'ज'}, {'झ'}, 'Unaspirated "ज" vs Aspirated "झ"'),
    ({'प'}, {'फ'}, 'Unaspirated "प" vs Aspirated "फ"'),
    ({'ब'}, {'भ'}, 'Unaspirated "ब" vs Aspirated "भ"'),
    
    # Sibilants
    ({'स'}, {'श', 'ष'}, 'Dental "स" vs Palatal/Retroflex "श/ष"'),
]

# Configurable Regional Dialect Equivalence Rules
# Form: (pattern_or_char_1, pattern_or_char_2, region_note)
DIALECT_EQUIVALENCES = [
    # Eastern Indo-Aryan /b/ vs /v/ (e.g. Bengali, Maithili, Bhojpuri, Odia influence)
    ('व', 'ब', 'Eastern regional variant (/v/ and /b/ interchangeable)'),
    ('ब', 'व', 'Eastern regional variant (/v/ and /b/ interchangeable)'),
    
    # Sibilant neutralization (/s/ vs /sh/)
    ('श', 'स', 'Regional sibilant softening (/sh/ -> /s/)'),
    ('ष', 'स', 'Regional sibilant softening (/sh/ -> /s/)'),
    ('स', 'श', 'Regional sibilant variation (/s/ -> /sh/)'),
    
    # Nasal neutralization
    ('ण', 'न', 'Regional nasal variation (/n/ for /ṇ/)'),
    ('न', 'ण', 'Regional nasal variation'),
    
    # Semivowel 'य' vs 'ज' (e.g. 'यमुना' <-> 'जमुना', 'यत्न' <-> 'जतन')
    ('य', 'ज', 'Regional semivowel shift (/y/ -> /j/)'),
    ('ज', 'य', 'Regional semivowel shift (/j/ -> /y/)'),
    
    # Nukta variations (e.g. 'ज़' -> 'ज', 'फ़' -> 'फ', 'ख़' -> 'ख')
    ('ज़', 'ज', 'Nukta simplification (ज़ -> ज)'),
    ('फ़', 'फ', 'Nukta simplification (फ़ -> फ)'),
    ('ख़', 'ख', 'Nukta simplification (ख़ -> ख)'),
    ('ग़', 'ग', 'Nukta simplification (ग़ -> ग)'),
]

# Known whole-word regional equivalences
KNOWN_WORD_DIALECT_MAP = {
    'वर्ष': ['बरस', 'वरस', 'बरष'],
    'वन': ['बन'],
    'विचार': ['बिचार'],
    'विवाह': ['बिवाह'],
    'शांति': ['सांति'],
    'शेर': ['सेर'],
    'रोशनी': ['रोसनी'],
    'कारण': ['कारन'],
    'प्रणाम': ['प्रनाम'],
    'यमुना': ['जमुना'],
    'कृपा': ['क्रिपा', 'क्रुपा'],
    'ऋषि': ['रिषि', 'रुषि'],
    'स्कूल': ['इसकूल', 'सकूल'],
    'स्टेशन': ['इस्टेशन', 'टेशन'],
}


def normalize_devanagari(text: str) -> str:
    """Standardizes Devanagari text using Unicode NFC normalization."""
    if not text:
        return ""
    # NFC composes base characters and combining matras into canonical forms
    return unicodedata.normalize('NFC', text.strip())


def extract_devanagari_matras(word: str) -> List[str]:
    """Returns list of matras present in a Devanagari word in sequence."""
    norm = normalize_devanagari(word)
    return [ch for ch in norm if ch in MATRAS]


def has_conjunct(word: str) -> bool:
    """Checks if a Devanagari word contains conjunct consonants (sanyuktakshar)."""
    norm = normalize_devanagari(word)
    # Check for explicit virama/halant (्)
    if DEV_VIRAMA in norm:
        return True
    # Check for pre-composed traditional ligatures
    for lig in ['क्ष', 'त्र', 'ज्ञ', 'श्र']:
        if lig in norm:
            return True
    return False


def get_conjunct_patterns(word: str) -> List[str]:
    """Extracts conjunct patterns found in the word."""
    norm = normalize_devanagari(word)
    patterns = []
    
    for lig, desc in SPECIAL_CONJUNCTS.items():
        if lig in norm:
            patterns.append(f"{lig} ({desc})")
            
    # Also find any C + virama + C clusters
    matches = re.findall(r'([\u0915-\u0939]\u094D[\u0915-\u0939])', norm)
    for m in matches:
        if m not in patterns:
            patterns.append(m)
            
    return patterns


def check_dialect_equivalence(expected: str, spoken: str) -> Optional[str]:
    """
    Checks if the spoken variation is an acceptable regional dialect variant.
    Returns the dialect rationale string if acceptable, else None.
    """
    exp_norm = normalize_devanagari(expected).lower()
    spk_norm = normalize_devanagari(spoken).lower()

    if not exp_norm or not spk_norm:
        return None

    # 1. Exact match after NFC
    if exp_norm == spk_norm:
        return "Exact match"

    # 2. Check known whole-word dialect dictionary
    if exp_norm in KNOWN_WORD_DIALECT_MAP:
        if spk_norm in KNOWN_WORD_DIALECT_MAP[exp_norm]:
            return f"Accepted regional dialect equivalent of '{expected}'"

    # 3. Check character-level dialect equivalences
    # Generate canonicalized version by applying known dialect substitutions
    canon_exp = exp_norm
    canon_spk = spk_norm
    for c1, c2, _ in DIALECT_EQUIVALENCES:
        canon_exp = canon_exp.replace(c1, c2)
        canon_spk = canon_spk.replace(c1, c2)

    if canon_exp == canon_spk:
        return "Dialect-fair match: Acceptable regional phonological variation"

    return None


def classify_indic_error(
    expected_word: str,
    spoken_word: Optional[str]
) -> Dict[str, Any]:
    """
    Diagnoses the pedagogical reason for an error in Devanagari or Indian reading.
    Returns structured record with:
      - error_type: MATRA | CONJUNCT | PHONETIC | OMISSION | DIALECT_EQUIVALENT | GENERAL_SUBSTITUTION
      - is_dialect_variant: bool (if True, should not be penalized)
      - target_pattern: string identifying the specific linguistic item
      - linguistic_detail: clear explanation of why the struggle occurred
      - pedagogical_remedy: constructive guidance for teacher/student
    """
    if not spoken_word:
        return {
            "error_type": "OMISSION",
            "is_dialect_variant": False,
            "target_pattern": expected_word,
            "linguistic_detail": f"Word '{expected_word}' was skipped during reading.",
            "pedagogical_remedy": "Encourage tracking each word gently with a finger or visual pointer."
        }

    exp_clean = normalize_devanagari(expected_word)
    spk_clean = normalize_devanagari(spoken_word)

    # 1. Dialect Equivalence Check
    dialect_reason = check_dialect_equivalence(exp_clean, spk_clean)
    if dialect_reason:
        return {
            "error_type": "DIALECT_EQUIVALENT",
            "is_dialect_variant": True,
            "target_pattern": exp_clean,
            "linguistic_detail": dialect_reason,
            "pedagogical_remedy": "Dialect-fair pronunciation acknowledged. Focus on fluency rather than accent correction."
        }

    # 2. Check for Matra Mismatch (Vowel Length / Diacritic)
    exp_matras = extract_devanagari_matras(exp_clean)
    spk_matras = extract_devanagari_matras(spk_clean)

    # Detect short vs long vowel confusion (e.g. ि vs ी or ु vs ू)
    for m_short, m_long, label in MATRA_PAIRS:
        if (m_short in exp_matras and m_long in spk_matras) or \
           (m_long in exp_matras and m_short in spk_matras):
            return {
                "error_type": "MATRA",
                "is_dialect_variant": False,
                "target_pattern": label,
                "linguistic_detail": f"Vowel length mismatch in '{expected_word}': read with '{MATRAS.get(spk_matras[0] if spk_matras else '', 'different vowel')}' instead of expected '{label}'.",
                "pedagogical_remedy": f"Guide the student on vowel duration: hrasva (short) vowels take a quick beat, while deergha (long) vowels are stretched."
            }

    # If matra counts or symbols differ while base consonants are similar
    if exp_matras != spk_matras:
        # Check if consonants match
        exp_cons = re.sub(r'[\u093E-\u094C\u0901-\u0903]', '', exp_clean)
        spk_cons = re.sub(r'[\u093E-\u094C\u0901-\u0903]', '', spk_clean)
        if exp_cons == spk_cons:
            return {
                "error_type": "MATRA",
                "is_dialect_variant": False,
                "target_pattern": "Matra Substitution",
                "linguistic_detail": f"Vowel sign variation on root consonant '{exp_cons}'.",
                "pedagogical_remedy": "Isolate the root letter and practice applying each matra in rhythm (Barakhadi warm-up)."
            }

    # 3. Check for Conjunct / Sanyuktakshar Struggle
    if has_conjunct(exp_clean):
        patterns = get_conjunct_patterns(exp_clean)
        pattern_str = ", ".join(patterns) if patterns else "Consonant cluster"
        
        # Check if student simplified/split the cluster (e.g. 'प्र' -> 'पर', 'स्त' -> 'सत' or 'स')
        return {
            "error_type": "CONJUNCT",
            "is_dialect_variant": False,
            "target_pattern": pattern_str,
            "linguistic_detail": f"Conjunct letter cluster difficulty in '{expected_word}' (contains {pattern_str}). Spoken as '{spoken_word}'.",
            "pedagogical_remedy": f"Practice blending the half-letter smoothly into the next consonant without adding an extra vowel sound in between."
        }

    # 4. Check for Phonetic Confusion (Dental vs Retroflex, Aspiration)
    for group1, group2, description in PHONETIC_PAIRS:
        has_g1_exp = any(ch in exp_clean for ch in group1)
        has_g2_spk = any(ch in spk_clean for ch in group2)
        has_g2_exp = any(ch in exp_clean for ch in group2)
        has_g1_spk = any(ch in spk_clean for ch in group1)

        if (has_g1_exp and has_g2_spk) or (has_g2_exp and has_g1_spk):
            return {
                "error_type": "PHONETIC",
                "is_dialect_variant": False,
                "target_pattern": description,
                "linguistic_detail": f"Phonetic articulation shift: {description}. Heard '{spoken_word}' for '{expected_word}'.",
                "pedagogical_remedy": "Demonstrate tongue placement: touch tongue behind front teeth for dental sounds (त), curl tongue back against palate for retroflex sounds (ट)."
            }

    # 5. Default Substitution
    return {
        "error_type": "SUBSTITUTION",
        "is_dialect_variant": False,
        "target_pattern": "Word Substitution",
        "linguistic_detail": f"Substituted '{expected_word}' with '{spoken_word}'.",
        "pedagogical_remedy": "Practice reading this word in small phrase contexts to build automatic word recognition."
    }
