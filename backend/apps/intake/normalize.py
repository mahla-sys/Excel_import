"""
Text normalization helpers.

These are pure, deterministic functions used during header matching (phase 2)
and later by the row normalization engine (phase 3). They always preserve the
original value alongside the normalized one — callers decide which to store.
"""
from __future__ import annotations

import re
import unicodedata

# Arabic/Persian digit variants -> Latin
_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# Common Arabic-letter variants used in Persian text.
_CHAR_MAP = str.maketrans({
    "ي": "ی",  # Arabic yeh -> Persian yeh
    "ى": "ی",  # Alef maqsura -> yeh (rough but useful)
    "ك": "ک",  # Arabic kaf -> Persian ke
    "ة": "ه",  # Teh marbuta -> heh
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ئ": "ی",
    "ء": "",
})

# Whitespace / control characters.
_INVISIBLE = [
    "\u200b",  # zero-width space
    "\u200c",  # zwnj (kept optionally; we replace with a regular space for matching)
    "\u200d",  # zwj
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u00a0",  # nbsp
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\ufeff",  # BOM
]


def normalize_header(value) -> str:
    """
    Normalize a header label for fuzzy matching.

    - NFKC unicode normalization
    - Persian/Arabic digits -> Latin (so "کدملی ۱" matches "کدملی 1")
    - Arabic letter variants -> Persian equivalents
    - Remove invisible/RTL control characters
    - Collapse all whitespace (including ZWNJ) to a single space
    - Lowercase and strip

    The ORIGINAL label is always retained separately for display/provenance.
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_DIGIT_MAP)
    text = text.translate(_CHAR_MAP)
    for ch in _INVISIBLE:
        text = text.replace(ch, " ")
    # Collapse whitespace and strip punctuation that shouldn't matter.
    text = re.sub(r"[\s\-_/\\.,()\[\]{}:;]+", " ", text)
    text = text.lower().strip()
    return text


def normalize_text(value) -> str:
    """
    Normalize a free-text cell value (e.g. a name) for storage.

    Unlike header matching, we keep ZWNJ because it is semantically meaningful
    in Persian words (e.g. «می‌رود»). Invisible/RTL controls and redundant
    spaces are still removed.
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_CHAR_MAP)
    # Remove truly invisible characters but keep ZWNJ (\u200c).
    for ch in _INVISIBLE:
        if ch == "\u200c":
            continue
        text = text.replace(ch, "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_digits(value) -> str:
    """Convert all Persian/Arabic digits to Latin, leaving other chars intact."""
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).translate(_DIGIT_MAP)


def normalize_national_id(value) -> tuple[str, list[str]]:
    """
    Normalize a national-id cell.

    Returns (normalized, notes) where notes describe modifications. The
    notes list powers W-* warnings at validation time (phase 4). This
    function deliberately does NOT validate the checksum; that lives in the
    validation engine. It only cleans the input.
    """
    if value is None:
        return "", ["empty"]
    text = normalize_digits(value)
    notes: list[str] = []
    original = text
    # Strip separators that users sometimes type.
    stripped = re.sub(r"[\s\-_]", "", text)
    if stripped != text:
        notes.append("separators_removed")
    text = stripped
    if not text:
        return "", notes + ["empty"]
    if not text.isdigit():
        return text, notes + ["non_digit_chars"]
    if len(text) < 10:
        # We DO NOT auto-pad silently; padding is a conscious decision and
        # the validation engine emits a warning when it pads.
        notes.append("too_short")
    if len(text) > 10:
        notes.append("too_long")
    if original != text:
        notes.append("normalized")
    return text, notes
