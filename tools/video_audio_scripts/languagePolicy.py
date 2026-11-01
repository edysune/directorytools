#!/usr/bin/env python3
"""Shared language & metadata policy for the video toolchain.

Single source of truth for how a stream's `language` value is interpreted.
Used by:

- fixVideoMetadata.py   (apply-mode fixer; compat shim `language_matches_whitelist`)
- runVideoMetadata.py   (non-interactive dry-run runner / classifier)
- (available for) analyzeVideoMetadata.py / gui_app.py

Policy (user decisions, 2026-10-28; see STRATEGY.md RISK-1/RISK-2/BUG-5):

1. Track-level tri-state. A stream's `language` value is one of:
   * keep        — normalizes to a whitelisted language            -> kept
   * confirmed   — normalizes to a SPECIFIC known language not in
                   the whitelist (fre, ara, jpn, dan, fin, ...)    -> removable
   * ambiguous   — cannot be confirmed as a specific language:
                   untagged (''/None/unknown/none), 'und' (ISO 639-2/B
                   "undetermined"), a leaked subtitle-format token
                   (ASS/SRT/SSA/VTT), a channel/mix label (Stereo,
                   Surround, MRSK, ...), or a fan-sub/alt-audio
                   "name" ("Nekomimi - No Honorifics", "Chihiro - German",
                   "English [CC]")                                 -> NEVER removed
   Rationale (user, verbatim intent): "if there is any ambiguity then we do
   NOT want to remove those subtitles"; suspected-English pending-removal
   tracks go on the EXCLUDE list for human review. Closing BUG-5 ('und')
   and RISK-2 (title/label leak) together.

2. RISK-1 (user-approved): removing ALL subtitles of a file is allowed ONLY
   when every subtitle track is confirmed (specific, non-whitelisted). If
   even one subtitle is ambiguous, that track — and the file's removal
   action for subtitles — is held.

3. Never leave a file with zero audio: audio removal applies only when at
   least one confirmed audio track remains (protects miscategorized
   content that has no whitelisted audio).

4. Foreign-by-nature content is excluded entirely (no default re-order,
   no audio/sub removal) while the language rules are still being
   validated. Confirmed category directories on the fleet drives:
   /mnt/A16000/plex/foreign_tv_shows, /mnt/A16000/plex/foreign_movies.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

# --- Known not-to-be-languages: leaked into `language` via title fallback ---
LEAK_TOKENS = {
    "ass", "ssa", "srt", "vtt",                          # subtitle formats
    "stereo", "surround", "dual mono", "dual-mono",      # channel mix
    "morsk", "morsk2", "mrsk", "audio", "main", "original",   # channel/mix labels (fleet-observed: MRSK)
    "commentary",
}

# untagged / ISO "undetermined"
UNKNOWN_LANGS = {"", "none", "unknown", "und"}

# a real BCP-47 primary subtag / language name never contains these
_TITLISH = re.compile(r"[\s\-/\\[\]{}|]")

# Canonical ISO 639-1 code per recognized token (ISO 639-1, 639-2/B/-3,
# and English names). Values are canonical 2-letter codes.
_LANG_TOKEN_TO_CODE = {
    # --- canonical 2-letter codes ---
    "en": "en", "ar": "ar", "da": "da", "nl": "nl", "fi": "fi", "fr": "fr",
    "de": "de", "it": "it", "es": "es", "pt": "pt", "ru": "ru", "ja": "ja",
    "ko": "ko", "zh": "zh", "cs": "cs", "he": "he", "hu": "hu", "pl": "pl",
    "sv": "sv", "tr": "tr", "ca": "ca", "el": "el", "hy": "hy", "vi": "vi",
    "th": "th", "ro": "ro", "sr": "sr", "uk": "uk", "hi": "hi", "bn": "bn",
    "ta": "ta", "te": "te", "mr": "mr", "gu": "gu", "kn": "kn", "ml": "ml",
    # --- ISO 639-2/B ---
    "eng": "en", "ara": "ar", "dan": "da", "nld": "nl", "fin": "fi",
    "fre": "fr", "fra": "fr", "deu": "de", "ger": "de", "ita": "it",
    "spa": "es", "cast": "es", "por": "pt", "rus": "ru", "jpn": "ja",
    "jap": "ja", "kor": "ko", "chi": "zh", "zho": "zh", "chinese": "zh",
    "ces": "cs", "cze": "cs", "czech": "cs",
    "heb": "he", "hul": "hu", "hun": "hu", "pol": "pl", "swe": "sv",
    "swedish": "sv", "tur": "tr", "cat": "ca",
    "ell": "el", "gre": "el", "greek": "el", "hye": "hy", "arm": "hy",
    "vie": "vi", "tha": "th", "ron": "ro", "rum": "ro", "srp": "sr",
    "scc": "sr", "sr": "sr", "hrv": "hr", "hr": "hr", "hrv": "hr",
    "ukr": "uk", "ukrainian": "uk",
    "hin": "hi", "hind": "hi", "hindi": "hi",
    "ben": "bn", "tam": "ta", "tel": "te", "mar": "mr", "guj": "gu",
    "kan": "kn", "mal": "ml", "kok": "kok",                            # kokani: no 2-letter
    # --- ISO 639-1 singletons / other real tokens present in the library ---
    "ind": "id", "id": "id",      # Indonesian
    "fil": "tl", "tl": "tl",      # Filipino (Tagalog)
    "may": "ms", "msa": "ms", "ms": "ms",   # Malay
    "dut": "nl",                                  # Dutch (639-1)
    "nob": "nb", "nor": "nb", "nb": "nb", "nn": "nb",   # Norwegian
    "enm": "enm",                                  # Middle English (NOT English)
    "est": "et", "et": "et",                       # Estonian
    "lit": "lt", "lt": "lt",                       # Lithuanian
    "lav": "lv", "lv": "lv",                       # Latvian
    "slv": "sl", "sl": "sl",                       # Slovenian
    "slo": "sl", "slk": "sk", "sk": "sk",          # slo=Slovenian(legacy), slk=Slovak
    "bul": "bg", "bg": "bg",                       # Bulgarian
    "baq": "eu", "eu": "eu",                       # Basque
    "glg": "gl", "gl": "gl",                       # Galician
    "mon": "mn", "mn": "mn",                       # Mongolian
    "mkd": "mk", "mk": "mk", "mac": "mk",          # Macedonian (mac=Macédoine legacy)
    "ice": "is", "isl": "is", "is": "is", "icelandic": "is",        # Icelandic
    # --- English names (case-insensitive) ---
    "english": "en", "arabic": "ar", "danish": "da", "dutch": "nl",
    "finnish": "fi", "french": "fr", "german": "de", "italian": "it",
    "spanish": "es", "castilian": "es", "portuguese": "pt", "russian": "ru",
    "japanese": "ja", "korean": "ko", "czech": "cs", "hebrew": "he",
    "hungarian": "hu", "polish": "pl", "turkish": "tr", "catalan": "ca",
    "armenian": "hy", "vietnamese": "vi", "thai": "th", "romanian": "ro",
    "serbian": "sr", "hindi": "hi", "bengali": "bn", "tamil": "ta",
    "telugu": "te", "marathi": "mr", "gujarati": "gu", "kannada": "kn",
    "malayalam": "ml",
}

# Category directories (any path component, case-insensitive) that are
# foreign-by-nature and therefore excluded from ALL metadata changes.
# Confirmed on the fleet: /mnt/A16000/plex/foreign_tv_shows,
# /mnt/A16000/plex/foreign_movies. Names kept broad ("foreign_shows" /
# "foreign_movies") so future drives with either spelling are covered.
EXCLUDED_CATEGORIES = frozenset({
    "foreign_shows",
    "foreign_tv_shows",
    "foreign_movies",
})


def normalize_lang_code(val) -> str | None:
    """Normalize a language value to a canonical code, or None if the value
    is not a single recognized language token.

    Only single tokens count: 'en', 'eng', 'EN', 'English', 'Japanese', 'jpn'…
    Anything compound ('English [CC]', 'Nekomimi - No Honorifics'), empty,
    'und', or an unknown word returns None (=> caller treats as ambiguous).
    """
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s:
        return None
    return _LANG_TOKEN_TO_CODE.get(s)


def is_unknown_lang(lang) -> bool:
    """True for untagged / 'unknown' / 'none' / 'und' values."""
    if lang is None:
        return True
    return str(lang).strip().lower() in UNKNOWN_LANGS


def is_ambiguous_lang(lang) -> bool:
    """True if the value is NOT a confirmed specific language: untagged/
    unknown/und, a leaked format/fan-sub/channel token, or a title-like
    compound. Such tracks may be English and must never be auto-removed."""
    if is_unknown_lang(lang):
        return True
    s = str(lang).strip()
    if not s:
        return True
    if s.lower() in LEAK_TOKENS:
        return True
    if _TITLISH.search(s):          # spaces / dashes / brackets => not a lang
        return True
    return False


def matches_whitelist(lang, whitelist: str) -> bool:
    """STRICT whitelist match. True only if `lang` is a confirmed language
    token that normalizes to the same canonical code as a whitelist entry.

    This replaces the old fuzzy prefix-matching implementation (which could
    mis-match or miss 'und'/labels). Unknown/ambiguous values always return
    False here — decide that with is_ambiguous_lang / lang_state first.
    """
    code = normalize_lang_code(lang)
    if code is None:
        return False
    for entry in str(whitelist or "").split(","):
        entry = entry.strip()
        if not entry or entry.lower() in ("unknown", "none", "und"):
            continue
        entry_code = normalize_lang_code(entry)
        if entry_code is not None and entry_code == code:
            return True
    return False


def lang_state(lang, whitelist: str) -> str:
    """Classify one track's language value:

    'ambiguous' — never removed (EXCLUDE list, human review). Covers
                  untagged/und, leak tokens, title-like compounds, and ANY
                  single token we cannot positively recognize as a specific
                  language (conservative per user policy: when in doubt, keep).
    'keep'      — confirmed + whitelisted
    'confirmed' — confirmed + non-whitelisted (removable)
    """
    if is_ambiguous_lang(lang):
        return "ambiguous"
    if normalize_lang_code(lang) is None:
        return "ambiguous"         # not a recognized language token -> keep (conservative)
    if matches_whitelist(lang, whitelist):
        return "keep"
    return "confirmed"


def _iter_path_parts(path) -> list[str]:
    s = str(path or "")
    classes = (PurePosixPath, PureWindowsPath)
    if "\\" in s:
        classes = (PureWindowsPath, PurePosixPath)   # win-style first, split really
    for cls in classes:
        try:
            parts = [p.lower() for p in cls(s).parts if p not in (".", "..", "")]
            if parts:
                return parts
        except ValueError:
            continue
    return [p.lower() for p in s.split("/") if p not in ("", ".", "..")]


def is_path_excluded(path) -> bool:
    """True if any path component is a foreign-category directory name.
    These paths are skipped by ALL metadata fixers (no audio/sub removal,
    no default re-order, no language guessing)."""
    return any(part in EXCLUDED_CATEGORIES for part in _iter_path_parts(path))
