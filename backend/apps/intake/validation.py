"""
Validation engine that runs AFTER a batch has been processed into
StagedStudent rows.

The normalizer (phase 3) produces field-level issues during extraction.
This validator adds BATCH-LEVEL and CROSS-ROW checks that need a view of
the whole batch (and previous batches of the same school):

* duplicate national IDs within the batch (blocking)
* suspected duplicates by name + birth date / phone (warning)
* missing emergency contact
* missing guardians
* classroom pending (info, accepted in MVP)

Identity matching rules (from the project spec, non-negotiable):

* Valid national ID match  -> possible_exact_identity_match (warning)
* Name + birth date / phone -> possible_duplicate (warning only)
* NEVER merge automatically; a human resolves it.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from django.db.models import Q

from .constants import IssueCode, IssueSeverity, PlacementStatus, RowStatus
from .models import ImportBatch, StagedStudent


@dataclass
class ValidationOutcome:
    issues_added: int = 0
    duplicates_found: int = 0
    status_counts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "issues_added": self.issues_added,
            "duplicates_found": self.duplicates_found,
            "status_counts": self.status_counts,
        }


_NAME_CLEAN_RE = re.compile(r"[\s_\-]+")


def _normalize_name_key(s: str) -> str:
    return _NAME_CLEAN_RE.sub("", (s or "").strip())


def _has_issue(issues: list[dict], code: str) -> bool:
    return any(i.get("code") == code for i in issues)


def validate_batch(batch: ImportBatch) -> ValidationOutcome:
    """Run cross-row validation over all StagedStudent rows of ``batch``.

    Idempotent: removes previously-injected validation warnings/duplicates
    (identified by code) before re-running, but preserves manually-added
    review notes.
    """
    students = list(
        batch.staged_students.all().prefetch_related("guardians").order_by("id")
    )

    outcome = ValidationOutcome()

    # Index 1: exact national ID within the batch.
    by_nid: dict[str, list[StagedStudent]] = defaultdict(list)
    for s in students:
        if s.national_id and s.national_id_valid:
            by_nid[s.national_id].append(s)

    # Index 2: name + birthdate or mobile for fuzzy match.
    by_name_birth: dict[tuple, list[StagedStudent]] = defaultdict(list)
    by_mobile: dict[str, list[StagedStudent]] = defaultdict(list)
    for s in students:
        name_key = _normalize_name_key(s.full_name)
        if name_key and s.birth_date:
            by_name_birth[(name_key, s.birth_date.isoformat())].append(s)
        for g in s.guardians.all():
            if g.mobile:
                by_mobile[g.mobile].append(s)
        # Also use the student's own mobile if present in contacts.
        mobile = (s.contacts or {}).get("emergency_mobile") or (s.contacts or {}).get(
            "student_mobile"
        )
        if mobile:
            by_mobile[mobile].append(s)

    # Also look across PREVIOUS batches of the same school for an exact NID
    # match. This is reported but never auto-merged.
    previous_nids: dict[str, int] = {}
    previous_qs = (
        StagedStudent.objects.filter(batch__school=batch.school)
        .exclude(batch=batch)
        .exclude(status=RowStatus.ARCHIVED)
        .filter(national_id_valid=True)
        .values("national_id", "batch_id")
    )
    for row in previous_qs:
        if row["national_id"]:
            previous_nids.setdefault(row["national_id"], row["batch_id"])

    # Reset injected issues so re-running validation is idempotent.
    injected_codes = {
        IssueCode.DUPLICATE_EXACT,
        IssueCode.DUPLICATE_SUSPECTED,
        IssueCode.EMERGENCY_CONTACT_MISSING,
        IssueCode.CLASSROOM_PENDING,
    }
    for s in students:
        cleaned = [i for i in (s.validation_issues or []) if i.get("code") not in injected_codes]
        if len(cleaned) != len(s.validation_issues or []):
            s.validation_issues = cleaned

    # Apply per-student checks.
    for s in students:
        issues: list[dict] = list(s.validation_issues or [])

        # Exact NID duplicate within the batch (blocking for the second+).
        if s.national_id and s.national_id_valid:
            same_batch = by_nid[s.national_id]
            if len(same_batch) > 1:
                other_ids = [x.id for x in same_batch if x.id != s.id]
                issues.append(_issue(
                    IssueCode.DUPLICATE_EXACT, IssueSeverity.WARNING,
                    field="student.national_id",
                    message=f"این کد ملی در {len(other_ids)} پرونده‌ی دیگر همین Batch هم آمده است. بررسی انسانی لازم است.",
                    extra={"other_student_ids": other_ids},
                ))
                outcome.duplicates_found += 1
            prev_batch_id = previous_nids.get(s.national_id)
            if prev_batch_id and prev_batch_id != batch.id:
                issues.append(_issue(
                    IssueCode.DUPLICATE_EXACT, IssueSeverity.WARNING,
                    field="student.national_id",
                    message="این کد ملی در یک Batch قبلی همین مدرسه هم ثبت شده است.",
                    extra={"previous_batch_id": prev_batch_id, "match_type": "exact_nid"},
                ))
                outcome.duplicates_found += 1

        # Name + birth date fuzzy duplicate (warning only).
        if s.full_name and s.birth_date:
            key = (_normalize_name_key(s.full_name), s.birth_date.isoformat())
            if len(by_name_birth[key]) > 1:
                other_ids = [x.id for x in by_name_birth[key] if x.id != s.id]
                if not any(
                    i.get("code") == IssueCode.DUPLICATE_SUSPECTED
                    and i.get("field") == "student.full_name"
                    for i in issues
                ):
                    issues.append(_issue(
                        IssueCode.DUPLICATE_SUSPECTED, IssueSeverity.WARNING,
                        field="student.full_name",
                        message="نام و تاریخ تولد مشابه پرونده‌ی دیگری در همین Batch است؛ نیاز به بررسی دارد.",
                        extra={"other_student_ids": other_ids, "match_type": "name_birthdate"},
                    ))
                    outcome.duplicates_found += 1

        # Mobile-based duplicate warning (only when no NID match above).
        if not s.national_id:
            for mobile, matches in by_mobile.items():
                if s in matches and len(matches) > 1:
                    other_ids = [x.id for x in matches if x.id != s.id]
                    issues.append(_issue(
                        IssueCode.DUPLICATE_SUSPECTED, IssueSeverity.WARNING,
                        field="contacts",
                        message="شماره تماس با پرونده‌ی دیگری مشترک است؛ لطفاً بررسی کنید.",
                        extra={"other_student_ids": other_ids, "match_type": "mobile"},
                    ))
                    outcome.duplicates_found += 1
                    break

        # Emergency contact missing (warning).
        contacts = s.contacts or {}
        emergency = contacts.get("emergency_mobile") or contacts.get("student_mobile")
        if not emergency:
            issues.append(_issue(
                IssueCode.EMERGENCY_CONTACT_MISSING, IssueSeverity.WARNING,
                field="contacts.emergency_mobile",
                message="شماره تماس ضروری ثبت نشده است.",
            ))

        # Classroom pending is EXPECTED in v1 (class placement not yet decided).
        if not s.classroom_title and s.status != RowStatus.INCOMPLETE:
            issues.append(_issue(
                IssueCode.CLASSROOM_PENDING, IssueSeverity.INFO,
                field="enrollment.classroom_title",
                message="کلاس/شعبه هنوز مشخص نشده؛ در این مرحله قابل قبول است.",
            ))

        s.validation_issues = issues
        s.status = _derive_status(s, batch)
        if s.status == PlacementStatus.PENDING:
            s.placement_status = PlacementStatus.PENDING
        s.save()
        outcome.status_counts[s.status] = outcome.status_counts.get(s.status, 0) + 1
        outcome.issues_added += len(issues)

    # Recompute batch status from its students.
    _update_batch_status(batch, students)

    return outcome


def _derive_status(s: StagedStudent, batch: ImportBatch) -> str:
    """Compute the staged student's status from its current issues.

    Error issues always block. Warnings are informational for the most
    part; the identity-level issues (duplicate NID, duplicate suspect,
    invalid NID) require human review, but softer warnings (missing
    emergency contact, pending classroom) do not.
    """
    issues = s.validation_issues or []
    blocking = [i for i in issues if i.get("severity") == IssueSeverity.ERROR]

    review_warnings = {
        IssueCode.DUPLICATE_EXACT,
        IssueCode.DUPLICATE_SUSPECTED,
        IssueCode.NID_CHECKSUM,
        IssueCode.NID_LENGTH,
        IssueCode.NID_DIGITS,
        IssueCode.BIRTHDATE_INVALID,
    }
    needs_review = any(i.get("code") in review_warnings for i in issues)

    if blocking:
        if not s.national_id:
            return RowStatus.INCOMPLETE
        return RowStatus.NEEDS_REVIEW
    if not s.first_name or not s.last_name:
        return RowStatus.INCOMPLETE
    if not s.national_id or s.national_id_valid is False:
        return RowStatus.INCOMPLETE
    if needs_review:
        return RowStatus.NEEDS_REVIEW
    if not s.classroom_title:
        return RowStatus.PENDING_PLACEMENT
    return RowStatus.VALIDATED


def _update_batch_status(batch: ImportBatch, students: Iterable[StagedStudent]) -> None:
    from django.utils import timezone

    students_list = list(students)
    if not students_list:
        batch.status = "review_required"
        batch.save(update_fields=["status", "updated_at"])
        return

    has_blocking = any(s.status == RowStatus.INCOMPLETE for s in students_list)
    has_warnings = any(s.status == RowStatus.NEEDS_REVIEW for s in students_list)

    if has_blocking or has_warnings:
        batch.status = "review_required"
    else:
        batch.status = "validated"
    batch.reviewed_at = timezone.now()
    batch.stats = {**(batch.stats or {}), **_count_statuses(students_list)}
    batch.save(update_fields=["status", "reviewed_at", "stats", "updated_at"])


def _count_statuses(students: Iterable[StagedStudent]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for s in students:
        counts[f"status_{s.status}"] += 1
    return dict(counts)


def _issue(code: str, severity: str, field: str, message: str, extra: dict | None = None) -> dict:
    out = {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
    }
    if extra:
        out.update(extra)
    return out
