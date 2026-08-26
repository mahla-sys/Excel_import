"""
Serializers for the manual review / edit workflow (phase 5).

Manual edits MUST:
* preserve the original raw value (it lives on ImportRow.raw_data and in
  field_provenance[*].raw_value);
* record last_edited_by / last_edited_at / edit_reason in field_provenance;
* write an AuditLog entry;
* trigger normalization + validation for the edited fields;
* recompute the student's status.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from .constants import IssueCode, RowStatus
from .models import StagedGuardian, StagedStudent
from .normalizers import (
    Normalized,
    normalize_birth_date,
    normalize_gender,
    normalize_grade,
    normalize_mobile,
    normalize_name,
    normalize_student_national_id,
)


# Fields that are manually editable. Each maps to a normalizer used when
# the value changes. Field paths here mirror the canonical schema.
EDITABLE_FIELDS: dict[str, callable] = {
    "first_name": normalize_name,
    "last_name": normalize_name,
    "national_id": normalize_student_national_id,
    "source_student_code": lambda v: Normalized(value=str(v).strip() if v else "", raw=str(v) if v is not None else ""),
    "birth_date": normalize_birth_date,
    "gender": normalize_gender,
    "grade": normalize_grade,
    "classroom_title": normalize_name,
    "emergency_mobile": normalize_mobile,
    "review_notes": None,  # free text, not normalized
}

# Fields whose change requires an explicit reason (sensitive identity data
# plus contact/grade per the project spec).
SENSITIVE_FIELDS = {
    "first_name",
    "last_name",
    "national_id",
    "birth_date",
    "gender",
    "grade",
    "emergency_mobile",
}

# Canonical path used in field_provenance for each editable model field.
PROVENANCE_PATH = {
    "first_name": "student.first_name",
    "last_name": "student.last_name",
    "national_id": "student.national_id",
    "source_student_code": "student.source_student_code",
    "birth_date": "student.birth_date",
    "gender": "student.gender",
    "grade": "enrollment.grade",
    "classroom_title": "enrollment.classroom_title",
    "emergency_mobile": "contacts.emergency_mobile",
    "review_notes": "review_notes",
}


# Codes that should be cleared before re-running field-level validation,
# because they may now be fixed by the edit.
RESOLVABLE_CODES = {
    IssueCode.STUDENT_NAME_MISSING,
    IssueCode.NID_CHECKSUM,
    IssueCode.NID_LENGTH,
    IssueCode.NID_MISSING,
    IssueCode.NID_NONDIGIT,
    IssueCode.NID_PADDED,
    IssueCode.BIRTHDATE_INVALID,
    IssueCode.GRADE_MISSING,
    IssueCode.GRADE_UNKNOWN,
    IssueCode.GENDER_INVALID,
}


class StudentPatchSerializer(serializers.Serializer):
    """Payload for PATCH /students/{id}/."""

    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    national_id = serializers.CharField(required=False, allow_blank=True, max_length=20)
    source_student_code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    birth_date = serializers.CharField(required=False, allow_blank=True, max_length=20)
    gender = serializers.CharField(required=False, allow_blank=True, max_length=10)
    grade = serializers.CharField(required=False, allow_blank=True, max_length=50)
    classroom_title = serializers.CharField(required=False, allow_blank=True, max_length=100)
    emergency_mobile = serializers.CharField(required=False, allow_blank=True, max_length=20)
    review_notes = serializers.CharField(required=False, allow_blank=True)
    # Required when a sensitive field is changed.
    edit_reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        changed_sensitive = SENSITIVE_FIELDS.intersection(attrs.keys())
        if changed_sensitive and not (attrs.get("edit_reason") or "").strip():
            raise serializers.ValidationError({
                "edit_reason": (
                    "برای تغییر "
                    + "، ".join(sorted(changed_sensitive))
                    + " باید دلیل اصلاح را بنویسید."
                )
            })
        return attrs


def apply_student_edit(student: StagedStudent, payload: dict, actor) -> StagedStudent:
    """
    Apply validated edits to a StagedStudent, update provenance, re-run
    field-level normalization/validation, recompute status, and persist.

    Cross-row duplicate checks are NOT re-run here; the caller (or the
    ``revalidate`` action) invokes validate_batch for that.
    """
    from .validation import _derive_status  # local import to avoid cycle

    edit_reason = (payload.get("edit_reason") or "").strip()
    now = timezone.now().isoformat()
    provenance = dict(student.field_provenance or {})
    issues = list(student.validation_issues or [])

    # Drop previously-resolved field issues (we re-add any that still apply).
    issues = [i for i in issues if i.get("code") not in RESOLVABLE_CODES]

    for field, normalizer in EDITABLE_FIELDS.items():
        if field not in payload:
            continue
        raw_value = payload[field]
        path = PROVENANCE_PATH[field]
        existing = provenance.get(path, {})

        if field == "review_notes":
            student.review_notes = raw_value or ""
            provenance[path] = {
                **existing,
                "last_edited_by": actor.username,
                "last_edited_at": now,
                "edit_reason": edit_reason or None,
            }
            continue

        # Normalize.
        n: Normalized
        if normalizer is None:
            n = Normalized(value=raw_value, raw=str(raw_value) if raw_value else "")
        else:
            n = normalizer(raw_value)

        # Apply to the model.
        if field == "birth_date":
            from datetime import date as _date
            student.birth_date = (
                _date.fromisoformat(n.value) if n.value else None
            )
            student.birth_date_raw = str(raw_value) if raw_value else ""
        elif field == "emergency_mobile":
            contacts = dict(student.contacts or {})
            contacts["emergency_mobile"] = n.value or ""
            student.contacts = contacts
        else:
            setattr(student, field, n.value)

        # Update national ID validity.
        if field == "national_id":
            if not n.value:
                student.national_id_valid = None
            else:
                student.national_id_valid = not any(
                    code.startswith("E-NID") for code in n.errors
                )

        # Re-attach field-level issues produced by the normalizer.
        for code in n.errors:
            issues.append({
                "code": code,
                "severity": "error",
                "field": path,
                "message": _message_for(code),
                "source_column": existing.get("column_label", ""),
                "source_row": student.source_row_id,
            })
        for code in n.warnings:
            issues.append({
                "code": code,
                "severity": "warning",
                "field": path,
                "message": _message_for(code),
                "source_column": existing.get("column_label", ""),
                "source_row": student.source_row_id,
            })

        provenance[path] = {
            **{k: v for k, v in existing.items() if k not in {"raw_value", "normalized_value"}},
            "raw_value": "" if raw_value is None else str(raw_value),
            "normalized_value": None if n.value is None else str(n.value),
            "last_edited_by": actor.username,
            "last_edited_at": now,
            "edit_reason": edit_reason or None,
        }

    student.field_provenance = provenance
    student.validation_issues = issues
    student.status = _derive_status(student, student.batch)

    # Classroom pending flag: if a classroom is supplied, mark placed.
    if student.classroom_title and student.status == RowStatus.PENDING_PLACEMENT:
        student.placement_status = "placed"

    student.reviewed_at = now
    student.save()
    return student


def _message_for(code: str) -> str:
    # Mirror messages from processor to keep a single source of truth.
    from .processor import _message_for as _proc_msg
    return _proc_msg(code)
