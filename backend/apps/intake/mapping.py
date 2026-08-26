"""
Column-mapping suggestions.

Given the detected columns of a workbook, propose canonical target fields
for each column. Suggestions are SUGGESTIONS only — the human operator makes
the final decision. Duplicate source headers (e.g. three "کدملی" columns) are
disambiguated by positional context: we look at neighboring columns (for
example, when a duplicate national ID appears right after "نام مادر" or in a
section labeled "مادر", we map it to guardian.mother.national_id).

The heuristic intentionally stays simple and transparent. The result includes
a ``confidence`` (``high|medium|low``) and a ``reason`` string that the UI can
show so operators understand *why* a suggestion was made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .constants import CANONICAL_FIELDS, HEADER_SUGGESTIONS
from .normalize import normalize_header


@dataclass
class Suggestion:
    column_index: int
    column_label: str
    target: str | None = None
    target_label: str | None = None
    confidence: str = "none"  # high | medium | low | none
    reason: str = ""
    alternatives: list[dict] = field(default_factory=list)


# Prefixes/keywords around a column that hint at which entity it belongs to.
# Ordered: earlier entries win.
_GUARDIAN_HINTS = [
    ("mother", ["مادر", "مامان", "والده", "mother", "mom"]),
    ("father", ["پدر", "پدرجان", "والد", "father", "dad"]),
    ("other", ["ولی", "قیم", "سرپرست", "guardian", "ولي"]),
]

_STUDENT_HINTS = [
    "دانش اموز", "دانش آموز", "دانشجو", "محصل", "student",
]


def _build_alias_index() -> dict[str, str]:
    """Invert HEADER_SUGGESTIONS into normalized-label -> canonical path."""
    index: dict[str, str] = {}
    for canonical, aliases in HEADER_SUGGESTIONS.items():
        for alias in aliases:
            key = normalize_header(alias)
            # Don't let a generic alias like "کد ملی" (already normalized)
            # overwrite a more specific mapping in case of collision; first
            # writer wins.
            index.setdefault(key, canonical)
        # Also index the canonical label itself.
        index.setdefault(normalize_header(CANONICAL_FIELDS[canonical]), canonical)
    return index


_ALIAS_INDEX = _build_alias_index()


def _detect_guardian_context(columns: list[dict], idx: int) -> str | None:
    """
    Look backward across the same section for a mother/father/guardian marker.

    Excel school files often use a layout like:

        | نام مادر | کدملی | شغل | نام پدر | کدملی | شغل |

    Scanning backwards from a duplicate column until the previous blank or
    strong entity separator tells us whose section we're in.
    """
    if idx <= 0:
        return None
    seen_marker: str | None = None
    for i in range(idx - 1, -1, -1):
        label = normalize_header(columns[i].get("label", ""))
        if not label:
            # blank column ends the current section
            if seen_marker:
                return seen_marker
            continue
        for relation, keywords in _GUARDIAN_HINTS:
            if any(kw in label for kw in keywords):
                return relation
        # A student-marker resets section context.
        if any(kw in label for kw in _STUDENT_HINTS):
            return None
    return seen_marker


def _exact_target_for(label: str) -> str | None:
    """Find a canonical target from a header's exact normalized form."""
    return _ALIAS_INDEX.get(normalize_header(label))


def _disambiguate_duplicate(
    label: str, target: str, context: str | None
) -> tuple[str | None, str]:
    """
    Given a generic target (often for a duplicate label), choose the
    guardian variant based on surrounding columns.

    Returns (new_target, reason).
    """
    if target in {"student.national_id", "student.first_name", "student.last_name", "student.full_name"}:
        field_name = target.split(".", 1)[1]
        if context in {"mother", "father", "other"}:
            return (
                f"guardian.{context}.{field_name}",
                f"بر اساس ستون‌های قبلی بخش «{context}» تشخیص داده شد.",
            )
    if target in {"contacts.student_mobile", "contacts.emergency_mobile", "contacts.home_phone"}:
        # Mobile/phone columns near father/mother sections are guardian mobiles.
        if context in {"father", "mother"}:
            return (
                f"guardian.{context}.mobile",
                f"ستون در بخش «{context}» قرار دارد و به‌عنوان موبایل ولی در نظر گرفته شد.",
            )
    return target, ""


def suggest_mappings(columns: list[dict]) -> list[Suggestion]:
    """
    Produce a suggestion per detected column.

    Each item in ``columns`` must be ``{index, label, samples?}`` matching the
    ``detected_columns`` shape stored on the batch.
    """
    # First pass: count labels and remember where each normalized label
    # first appears. The first occurrence of a duplicate like "کدملی" is
    # the student's; later ones belong to father/mother sections.
    normalized_counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for col in columns:
        key = normalize_header(col.get("label", ""))
        if key:
            normalized_counts[key] = normalized_counts.get(key, 0) + 1
            first_seen.setdefault(key, col["index"])

    results: list[Suggestion] = []
    for col in columns:
        idx = col["index"]
        label = col.get("label", "")
        suggestion = Suggestion(column_index=idx, column_label=label)

        target = _exact_target_for(label)
        if target is None:
            results.append(suggestion)
            continue

        norm = normalize_header(label)
        is_duplicate = normalized_counts.get(norm, 0) > 1
        is_first_occurrence = first_seen.get(norm) == idx

        if is_duplicate:
            context = _detect_guardian_context(columns, idx)
            if context is None and is_first_occurrence:
                # First occurrence, before any mother/father marker:
                # this is the student's own column.
                suggestion.target = target
                suggestion.confidence = "high"
                suggestion.reason = (
                    "نخستین ستون با این عنوان (بخش دانش‌آموز)."
                )
            else:
                new_target, reason = _disambiguate_duplicate(label, target, context)
                if new_target != target:
                    suggestion.target = new_target
                    suggestion.confidence = "medium"
                    suggestion.reason = reason or "ستون تکراری با موقعیت تفکیک شد."
                else:
                    suggestion.target = target
                    suggestion.confidence = "low"
                    suggestion.reason = (
                        "چند ستون با همین عنوان وجود دارد؛ بررسی دستی لازم است."
                    )
        else:
            suggestion.target = target
            suggestion.confidence = "high"
            suggestion.reason = "تطابق دقیق با عنوان شناخته‌شده."

        if suggestion.target:
            suggestion.target_label = CANONICAL_FIELDS.get(suggestion.target)

        # Build a short list of alternatives (other known targets).
        alts: list[dict] = []
        for path, lbl in CANONICAL_FIELDS.items():
            if path == suggestion.target:
                continue
            # Keep alternatives tight: only those that share a word with the label.
            if norm and any(tok in normalize_header(lbl) or normalize_header(lbl) in norm
                           for tok in norm.split() if len(tok) > 1):
                alts.append({"path": path, "label": lbl})
        suggestion.alternatives = alts[:6]
        results.append(suggestion)

    return results


def ensure_no_duplicate_targets(mapping: dict[str, dict]) -> list[str]:
    """
    Validate that two canonical fields are not mapped to the same source
    column. Returns a list of human-readable Persian warnings (empty list
    when the mapping is consistent).
    """
    seen: dict[int, list[str]] = {}
    for canonical, target in mapping.items():
        idx = target.get("source_column_index")
        if idx is None:
            continue
        seen.setdefault(idx, []).append(canonical)
    warnings: list[str] = []
    for idx, targets in seen.items():
        if len(targets) > 1:
            warnings.append(
                f"ستون شمارهٔ {idx + 1} به چند فیلد استاندارد نگاشت شده: "
                + "، ".join(targets)
            )
    return warnings
