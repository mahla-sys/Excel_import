"""
Normalization engine for Iranian school data.

Each normalizer returns (normalized_value, warnings, raw_preserved). The
original raw value is ALWAYS retained separately by the caller — these
functions do not mutate input.

Canonical schema version is exported as CANONICAL_SCHEMA_VERSION; the
future connector keys off this number to parse exports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import jdatetime

from .normalize import normalize_digits, normalize_national_id, normalize_text

# Bump on any breaking change to the canonical student JSON shape.
CANONICAL_SCHEMA_VERSION = "1.0"


class NormalizeError(ValueError):
    """Raised when a value cannot be normalized (e.g. invalid national ID)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class Normalized:
    value: Any = None
    raw: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Extra provenance detail (e.g. "padded_to_10_digits").
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# National ID — Iranian 10-digit code with checksum.
# --------------------------------------------------------------------------

def validate_iranian_national_id(nid: str) -> tuple[bool, str]:
    """
    Return (is_valid, reason).

    Implements the official checksum algorithm:
      digits d[0..9], check = d[9]
      sum = sum(d[i] * (10-i) for i in 0..9)
      r = sum % 11
      valid if r < 2 and check == r, or r >= 2 and check == 11-r
    """
    if not nid or not nid.isdigit() or len(nid) != 10:
        return False, "طول کد ملی باید ۱۰ رقم باشد."
    # All-same-digit IDs like 0000000000 are structurally valid-sum but invalid
    # in practice; reject them.
    if len(set(nid)) == 1:
        return False, "کد ملی تماماً یک رقم است."
    digits = [int(c) for c in nid]
    check = digits[-1]
    total = sum(digits[i] * (10 - i) for i in range(9))
    remainder = total % 11
    if remainder < 2:
        expected = remainder
    else:
        expected = 11 - remainder
    if check != expected:
        return False, "رقم کنترل کد ملی نامعتبر است."
    return True, ""


def normalize_student_national_id(raw: Any) -> Normalized:
    if raw is None or str(raw).strip() == "":
        return Normalized(raw="", warnings=["W-NID-MISSING"])
    cleaned, notes = normalize_national_id(raw)
    n = Normalized(raw=str(raw), value=cleaned, notes=notes)

    if not cleaned:
        n.warnings.append("W-NID-MISSING")
        return n
    if "non_digit_chars" in notes:
        n.warnings.append("W-NID-NONDIGIT")
    if "too_long" in notes:
        n.errors.append("E-NID-LENGTH")
        return n
    if "too_short" in notes:
        # Pad with leading zeros ONLY with an explicit note; the validation
        # layer decides if this is acceptable for the row.
        if len(cleaned) >= 8:
            padded = cleaned.zfill(10)
            n.value = padded
            n.notes.append("padded_to_10_digits")
            n.warnings.append("W-NID-PADDED")
        else:
            n.errors.append("E-NID-LENGTH")
            return n

    valid, reason = validate_iranian_national_id(n.value)
    if not valid:
        n.errors.append("E-NID-CHECKSUM")
    return n


# --------------------------------------------------------------------------
# Phone / mobile — Iranian mobile format 09xxxxxxxxx.
# --------------------------------------------------------------------------

_MOBILE_RE = re.compile(r"^(?:\+98|98|0)?9\d{9}$")


def normalize_mobile(raw: Any) -> Normalized:
    if raw is None or str(raw).strip() == "":
        return Normalized(raw="")
    digits = normalize_digits(raw)
    cleaned = re.sub(r"[\s\-_()]", "", digits)
    n = Normalized(raw=str(raw), value=cleaned)
    if not cleaned:
        return n
    # Normalize +98 / 98 prefix to leading 0 for canonical storage.
    if cleaned.startswith("+98"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]
    elif cleaned.startswith("9") and len(cleaned) == 10:
        cleaned = "0" + cleaned
    n.value = cleaned
    if not _MOBILE_RE.match(cleaned):
        n.warnings.append("W-PHONE-INVALID")
    return n


# --------------------------------------------------------------------------
# Gender
# --------------------------------------------------------------------------

_GENDER_MAP = {
    "مذکر": "male", "پسر": "male", "پسرانه": "male", "male": "male", "m": "male", "آقا": "male",
    "مونث": "female", "مؤنث": "female", "دختر": "female", "دخترانه": "female",
    "female": "female", "f": "female", "خانم": "female",
}


def normalize_gender(raw: Any) -> Normalized:
    if raw is None or str(raw).strip() == "":
        return Normalized(raw="")
    key = normalize_text(raw).lower().strip()
    value = _GENDER_MAP.get(key)
    n = Normalized(raw=str(raw), value=value)
    if value is None:
        n.warnings.append("W-GENDER-INVALID")
        n.value = None
    return n


# --------------------------------------------------------------------------
# Birth date — accepts Jalali (1380/06/15, 1380-06-15, ۱۳۸۰/۶/۱۵)
# and Gregorian (2001-09-05). Returns ISO date string (YYYY-MM-DD).
# --------------------------------------------------------------------------

_DATE_SPLIT = re.compile(r"[/-]")


def normalize_birth_date(raw: Any) -> Normalized:
    if raw is None or str(raw).strip() == "":
        return Normalized(raw="")
    if isinstance(raw, datetime):
        raw = raw.date()
    if isinstance(raw, date):
        return Normalized(raw=raw.isoformat(), value=raw.isoformat())

    raw_str = str(raw).strip()
    digits = normalize_digits(raw_str)
    n = Normalized(raw=raw_str)

    parts = [p for p in _DATE_SPLIT.split(digits) if p]
    if len(parts) != 3:
        n.errors.append("E-BIRTHDATE-INVALID")
        return n
    try:
        a, b, c = (int(p) for p in parts)
    except ValueError:
        n.errors.append("E-BIRTHDATE-INVALID")
        return n

    # Heuristic: Jalali years are 13xx, Gregorian years are 19xx/20xx.
    if 1300 <= a <= 1500:
        try:
            jd = jdatetime.date(a, b, c)
            gd = jd.togregorian()
            n.value = gd.isoformat()
            n.notes.append(f"converted_from_jalali:{jd.isoformat()}")
            return n
        except ValueError:
            n.errors.append("E-BIRTHDATE-INVALID")
            return n
    if 1900 <= a <= 2100:
        try:
            gd = date(a, b, c)
            n.value = gd.isoformat()
            return n
        except ValueError:
            n.errors.append("E-BIRTHDATE-INVALID")
            return n
    n.errors.append("E-BIRTHDATE-INVALID")
    return n


# --------------------------------------------------------------------------
# Grade — controlled vocabulary
# --------------------------------------------------------------------------

from .constants import GRADE_ALIASES, GRADES  # noqa: E402


def normalize_grade(raw: Any) -> Normalized:
    if raw is None or str(raw).strip() == "":
        return Normalized(raw="", warnings=["W-GRADE-MISSING"])
    text = normalize_text(raw)
    key = text.strip().lower()
    canonical = GRADE_ALIASES.get(key) or GRADE_ALIASES.get(text)
    if canonical:
        return Normalized(raw=str(raw), value=canonical)
    # Maybe the raw is already a canonical label.
    if text in GRADES:
        return Normalized(raw=str(raw), value=text)
    # Unknown grade — keep raw, warn.
    n = Normalized(raw=str(raw), value=text, warnings=["W-GRADE-UNKNOWN"])
    return n


# --------------------------------------------------------------------------
# Name / free text
# --------------------------------------------------------------------------

def normalize_name(raw: Any) -> Normalized:
    if raw is None:
        return Normalized(raw="")
    cleaned = normalize_text(raw)
    # Collapse internal whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return Normalized(raw=str(raw), value=cleaned)


# --------------------------------------------------------------------------
# Academic year — 1405-1406. Persian digits accepted.
# --------------------------------------------------------------------------

_ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})-(\d{4})$")


def normalize_academic_year(raw: Any) -> Normalized:
    if raw is None:
        return Normalized(raw="", errors=["E-ACADEMIC-YEAR-MISSING"])
    digits = normalize_digits(str(raw)).replace(" ", "")
    n = Normalized(raw=str(raw))
    m = _ACADEMIC_YEAR_RE.match(digits)
    if not m:
        n.errors.append("E-ACADEMIC-YEAR-MISSING")
        return n
    start, end = int(m.group(1)), int(m.group(2))
    if end != start + 1:
        n.warnings.append("W-ACADEMIC-YEAR-RANGE")
    n.value = f"{start}-{end}"
    return n
