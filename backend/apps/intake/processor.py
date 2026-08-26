"""
Row extraction and normalization pipeline.

Pipeline:
  1. Open the private workbook with openpyxl (read_only).
  2. For each row after the header, build an ImportRow with raw_data.
  3. Apply the batch's mapping to assemble a canonical student dict.
  4. Run each field through its normalizer, collecting issues.
  5. Create a StagedStudent (and StagedGuardian rows) when at least a
     first name is present. Rows without a name are still kept as
     ImportRow with a blocking error.
  6. Each row is wrapped in its own savepoint so a single bad row
     never aborts the whole batch.

This module is sync on purpose (no Celery in MVP).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from django.core.files.base import File
from django.db import transaction
from openpyxl import load_workbook

from .constants import (
    AdmissionStatus,
    BatchStatus,
    IssueCode,
    IssueSeverity,
    PlacementStatus,
    RowStatus,
)
from .models import ImportBatch, ImportRow, StagedGuardian, StagedStudent
from .validation import validate_batch
from .normalizers import (
    Normalized,
    normalize_academic_year,
    normalize_birth_date,
    normalize_gender,
    normalize_grade,
    normalize_mobile,
    normalize_name,
    normalize_student_national_id,
)

logger = logging.getLogger("apps.intake.processor")


@dataclass
class RowIssue:
    code: str
    severity: str
    field: str = ""
    message: str = ""
    source_column: str = ""
    source_row: int = 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "source_column": self.source_column,
            "source_row": self.source_row,
        }


@dataclass
class ProcessingStats:
    total_rows: int = 0
    created_students: int = 0
    errors: int = 0
    warnings: int = 0
    incomplete: int = 0
    validated: int = 0
    pending_placement: int = 0
    failed_rows: int = 0

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "created_students": self.created_students,
            "errors": self.errors,
            "warnings": self.warnings,
            "incomplete": self.incomplete,
            "validated": self.validated,
            "pending_placement": self.pending_placement,
            "failed_rows": self.failed_rows,
        }


# Mapping of canonical field path -> (normalizer, is_required).
STUDENT_FIELD_NORMALIZERS = {
    "student.first_name": (normalize_name, True),
    "student.last_name": (normalize_name, True),
    "student.full_name": (normalize_name, False),
    "student.national_id": (normalize_student_national_id, False),
    "student.source_student_code": (lambda r: Normalized(value=str(r).strip() if r else "", raw=str(r) if r is not None else ""), False),
    "student.birth_date": (normalize_birth_date, False),
    "student.gender": (normalize_gender, False),
    "student.birth_place": (normalize_name, False),
    "enrollment.grade": (normalize_grade, False),
    "enrollment.classroom_title": (normalize_name, False),
    "enrollment.admission_status": (
        lambda r: Normalized(value=str(r).strip() if r else "", raw=str(r) if r is not None else ""),
        False,
    ),
    "contacts.student_mobile": (normalize_mobile, False),
    "contacts.emergency_mobile": (normalize_mobile, False),
    "contacts.emergency_contact_relation": (normalize_name, False),
    "contacts.home_phone": (normalize_mobile, False),
    "contacts.home_address": (normalize_name, False),
    "contacts.postal_code": (normalize_name, False),
    "contacts.student_lives_with": (normalize_name, False),
    "admission.quota": (normalize_name, False),
    "admission.previous_school_name": (normalize_name, False),
    "admission.previous_average": (normalize_name, False),
    "admission.previous_discipline_score": (normalize_name, False),
}

GUARDIAN_FIELDS = {
    "first_name", "last_name", "full_name", "national_id",
    "birth_date", "mobile", "education_level", "field_of_study",
    "employment_status", "occupation", "workplace_address",
}


def _hash_row(values: Iterable[Any]) -> str:
    h = hashlib.sha256()
    for v in values:
        h.update(("|" + ("" if v is None else str(v))).encode("utf-8", errors="replace"))
    return h.hexdigest()


def _cell_value(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _is_row_empty(values: list[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in values)


def process_batch(batch: ImportBatch) -> ProcessingStats:
    """
    Extract rows, normalize, and stage students. Idempotent: prior
    ImportRow / StagedStudent records for the batch are replaced.
    """
    if not batch.mapping_snapshot or not batch.mapping_snapshot.get("mappings"):
        raise ValueError("Batch has no saved mapping; cannot process.")
    if not (batch.selected_sheet and batch.header_row_number):
        raise ValueError("Batch sheet/header not selected.")

    batch.status = BatchStatus.PROCESSING
    batch.failure_reason = ""
    batch.save(update_fields=["status", "failure_reason", "updated_at"])

    mappings = batch.mapping_snapshot["mappings"]
    unknown_actions = {
        u["index"]: u.get("action", "extra_attribute")
        for u in batch.mapping_snapshot.get("unknown_columns", [])
    }

    stats = ProcessingStats()
    try:
        with transaction.atomic():
            # Idempotency: clear previous staged output for this batch.
            batch.staged_students.all().delete()
            batch.rows.all().delete()

            with batch.open_private_file() as django_file:
                wb = load_workbook(
                    File(django_file),
                    read_only=True,
                    data_only=True,
                    keep_links=False,
                )
                try:
                    ws = wb[batch.selected_sheet]
                    rows_iter = ws.iter_rows(
                        min_row=batch.header_row_number + 1,
                        values_only=True,
                    )
                    for row_offset, raw_row in enumerate(rows_iter, start=batch.header_row_number + 1):
                        values = [_cell_value(v) for v in raw_row]
                        if _is_row_empty(values):
                            continue
                        stats.total_rows += 1
                        try:
                            with transaction.atomic():
                                _process_one_row(
                                    batch, row_offset, values,
                                    mappings, unknown_actions, stats,
                                )
                        except Exception:
                            logger.exception("Row %d failed to process", row_offset)
                            stats.failed_rows += 1
                            ImportRow.objects.create(
                                batch=batch,
                                row_number=row_offset,
                                raw_data=values,
                                validation_issues=[
                                    RowIssue(
                                        code=IssueCode.ROW_EMPTY,
                                        severity=IssueSeverity.ERROR,
                                        message="خطای فنی در پردازش سطر.",
                                        source_row=row_offset,
                                    ).to_dict()
                                ],
                                status=RowStatus.NEEDS_REVIEW,
                                source_hash=_hash_row(values),
                            )
                finally:
                    wb.close()

            from django.utils import timezone
            batch.stats = stats.to_dict()
            batch.processed_at = timezone.now()
            batch.save(update_fields=["stats", "processed_at", "updated_at"])

            # Cross-row / cross-batch validation (duplicates, missing
            # contacts, etc.) runs on the freshly staged data.
            validation_outcome = validate_batch(batch)
            batch.stats = {**batch.stats, "validation": validation_outcome.to_dict()}
            batch.save(update_fields=["stats", "updated_at"])
    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.failure_reason = str(exc)[:1000]
        batch.save(update_fields=["status", "failure_reason", "updated_at"])
        logger.exception("Batch %d processing failed", batch.id)
        raise

    return stats


def _process_one_row(
    batch: ImportBatch,
    row_number: int,
    values: list[Any],
    mappings: dict,
    unknown_actions: dict,
    stats: ProcessingStats,
) -> None:
    """Normalize a single row and persist its ImportRow + StagedStudent."""
    issues: list[RowIssue] = []
    provenance: dict[str, dict] = {}
    canonical: dict[str, Any] = {
        "student": {}, "enrollment": {}, "contacts": {},
        "guardians": {"father": {}, "mother": {}, "other": {}},
        "admission": {}, "extra_attributes": {},
    }

    # Build a label lookup for source columns.
    col_labels = {c["index"]: c.get("label", f"col_{c['index']}") for c in batch.detected_columns}

    # Apply mappings.
    for canonical_path, target in mappings.items():
        idx = target["source_column_index"]
        raw = values[idx] if idx < len(values) else None
        source_label = target.get("source_column_label") or col_labels.get(idx, "")
        normalizer, required = STUDENT_FIELD_NORMALIZERS.get(canonical_path, (None, False))

        n: Normalized
        if normalizer is not None:
            n = normalizer(raw)
        else:
            n = Normalized(value=raw, raw="" if raw is None else str(raw))

        for code in n.errors:
            issues.append(RowIssue(
                code=code, severity=IssueSeverity.ERROR,
                field=canonical_path, message=_message_for(code),
                source_column=source_label, source_row=row_number,
            ))
            stats.errors += 1
        for code in n.warnings:
            issues.append(RowIssue(
                code=code, severity=IssueSeverity.WARNING,
                field=canonical_path, message=_message_for(code),
                source_column=source_label, source_row=row_number,
            ))
            stats.warnings += 1

        # Place value in the right canonical bucket.
        provenance[canonical_path] = {
            "batch_id": batch.id, "row_number": row_number,
            "column_index": idx, "column_label": source_label,
            "raw_value": None if raw is None else str(raw),
            "normalized_value": None if n.value is None else str(n.value),
        }
        _place_canonical(canonical, canonical_path, n.value)

    # Unknown columns are kept (never silently dropped).
    for col in batch.detected_columns:
        idx = col["index"]
        already_mapped = any(t["source_column_index"] == idx for t in mappings.values())
        if already_mapped:
            continue
        if idx >= len(values):
            continue
        raw = values[idx]
        action = unknown_actions.get(idx, "extra_attribute")
        if action == "ignored":
            continue
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        canonical["extra_attributes"][col["label"]] = str(raw)
        provenance[f"extra.{col['label']}"] = {
            "batch_id": batch.id, "row_number": row_number,
            "column_index": idx, "column_label": col["label"],
            "raw_value": str(raw), "normalized_value": str(raw),
        }

    # ---- Determine whether we can construct a StagedStudent ----
    student = canonical["student"]
    enrollment = canonical["enrollment"]
    first_name = (student.get("first_name") or "").strip()
    last_name = (student.get("last_name") or "").strip()
    full_name = (student.get("full_name") or "").strip()

    has_name = bool(first_name or last_name or full_name)
    if not has_name:
        issues.append(RowIssue(
            code=IssueCode.STUDENT_NAME_MISSING, severity=IssueSeverity.ERROR,
            field="student.first_name",
            message="نام یا نام خانوادگی دانش‌آموز موجود نیست.",
            source_row=row_number,
        ))
        stats.errors += 1

    # Academic year from batch (always present after upload validation).
    ay = normalize_academic_year(batch.academic_year_label)
    for code in ay.errors:
        issues.append(RowIssue(
            code=code, severity=IssueSeverity.ERROR,
            field="enrollment.academic_year",
            message="سال تحصیلی معتبر نیست.", source_row=row_number,
        ))

    row_status = _row_status_from_issues(issues)

    import_row = ImportRow.objects.create(
        batch=batch,
        row_number=row_number,
        raw_data=values,
        normalized_data=canonical,
        validation_issues=[i.to_dict() for i in issues],
        status=row_status,
        source_hash=_hash_row(values),
    )

    if has_name:
        student_obj = StagedStudent(
            batch=batch, source_row=import_row,
            first_name=first_name, last_name=last_name,
            full_name=full_name or f"{first_name} {last_name}".strip(),
            national_id=student.get("national_id") or "",
            national_id_valid=None,  # set below from issues
            source_student_code=student.get("source_student_code") or "",
            birth_date=_coerce_date(student.get("birth_date")),
            birth_date_raw=provenance.get("student.birth_date", {}).get("raw_value", ""),
            gender=student.get("gender") or "",
            birth_place=student.get("birth_place") or "",
            academic_year=ay.value or batch.academic_year_label,
            grade=enrollment.get("grade") or "",
            classroom_title=enrollment.get("classroom_title") or "",
            placement_status=PlacementStatus.PENDING,
            admission_status=enrollment.get("admission_status") or AdmissionStatus.CONFIRMED,
            contacts=canonical["contacts"],
            admission_data=canonical["admission"],
            extra_attributes=canonical["extra_attributes"],
            field_provenance=provenance,
            validation_issues=[i.to_dict() for i in issues],
            status=row_status,
        )
        # National ID validity from issues.
        nid_codes = {i.code for i in issues if i.field == "student.national_id"}
        if IssueCode.NID_CHECKSUM in nid_codes or IssueCode.NID_LENGTH in nid_codes:
            student_obj.national_id_valid = False
        elif student_obj.national_id:
            student_obj.national_id_valid = True

        # Status: incomplete if missing national_id or has blocking errors.
        if any(i.severity == IssueSeverity.ERROR for i in issues):
            student_obj.status = RowStatus.INCOMPLETE if not student_obj.national_id else RowStatus.NEEDS_REVIEW
            stats.incomplete += 1
        elif not student_obj.national_id:
            student_obj.status = RowStatus.INCOMPLETE
            stats.incomplete += 1
        elif not student_obj.classroom_title:
            student_obj.status = RowStatus.PENDING_PLACEMENT
            stats.pending_placement += 1
        else:
            student_obj.status = RowStatus.VALIDATED
            stats.validated += 1

        student_obj.save()
        import_row.staged_student = student_obj
        import_row.status = student_obj.status
        import_row.save(update_fields=["staged_student", "status", "updated_at"])
        stats.created_students += 1

        # Guardians
        for relation in ("father", "mother", "other"):
            gdata = canonical["guardians"].get(relation) or {}
            if not any(gdata.values()):
                continue
            g_prov: dict[str, dict] = {}
            for k, v in gdata.items():
                if k in provenance:
                    g_prov[k] = provenance[k]
            guardian = StagedGuardian(
                student=student_obj,
                relation_type=relation if relation in {"father", "mother"} else "other",
                first_name=gdata.get("first_name") or "",
                last_name=gdata.get("last_name") or "",
                full_name=gdata.get("full_name") or "",
                national_id=gdata.get("national_id") or "",
                birth_date=_coerce_date(gdata.get("birth_date")),
                birth_date_raw=g_prov.get("birth_date", {}).get("raw_value", ""),
                mobile=gdata.get("mobile") or "",
                education_level=gdata.get("education_level") or "",
                field_of_study=gdata.get("field_of_study") or "",
                employment_status=gdata.get("employment_status") or "",
                occupation=gdata.get("occupation") or "",
                workplace_address=gdata.get("workplace_address") or "",
                field_provenance=g_prov,
            )
            guardian.save()
    else:
        stats.incomplete += 1


def _place_canonical(canonical: dict, path: str, value: Any) -> None:
    if value is None or value == "":
        return
    if path.startswith("guardian."):
        # guardian.father.first_name -> bucket "father", field "first_name"
        parts = path.split(".", 2)
        if len(parts) == 3:
            _, relation, field = parts
            canonical["guardians"].setdefault(relation, {})[field] = value
        return
    if "." in path:
        bucket, field = path.split(".", 1)
        if bucket in canonical and isinstance(canonical[bucket], dict):
            canonical[bucket][field] = value
            return
    canonical.setdefault("extra_attributes", {})[path] = value


def _coerce_date(value: Any):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _row_status_from_issues(issues: list[RowIssue]) -> str:
    if any(i.severity == IssueSeverity.ERROR for i in issues):
        return RowStatus.INCOMPLETE
    if any(i.severity == IssueSeverity.WARNING for i in issues):
        return RowStatus.NEEDS_REVIEW
    return RowStatus.DRAFT


def _message_for(code: str) -> str:
    messages = {
        IssueCode.STUDENT_NAME_MISSING: "نام یا نام خانوادگی دانش‌آموز موجود نیست.",
        IssueCode.NID_CHECKSUM: "کد ملی معتبر نیست (رقم کنترل نادرست).",
        IssueCode.NID_LENGTH: "کد ملی باید ۱۰ رقم باشد.",
        IssueCode.NID_MISSING: "کد ملی وارد نشده؛ پرونده تا زمان تکمیل قابل انتقال نیست.",
        IssueCode.NID_NONDIGIT: "کد ملی شامل کاراکترهای غیرعددی بود که پاک‌سازی شد.",
        IssueCode.NID_PADDED: "کد ملی کوتاه‌تر از ۱۰ رقم بود؛ با صفر ابتدایی تکمیل شد.",
        IssueCode.GRADE_MISSING: "پایه تحصیلی مشخص نشده است.",
        IssueCode.GRADE_UNKNOWN: "مقدار پایه در واژگان استاندارد نبود؛ مقدار خام نگه داشته شد.",
        IssueCode.CLASSROOM_PENDING: "کلاس/شعبه هنوز مشخص نشده؛ در این مرحله قابل قبول است.",
        IssueCode.EMERGENCY_CONTACT_MISSING: "شماره تماس ضروری ثبت نشده است.",
        IssueCode.PHONE_INVALID: "شماره تماس با الگوی موبایل ایران مطابقت ندارد.",
        IssueCode.GENDER_INVALID: "جنسیت قابل تشخیص نبود.",
        IssueCode.BIRTHDATE_INVALID: "تاریخ تولد قابل تفسیر نیست.",
        IssueCode.ACADEMIC_YEAR_MISSING: "سال تحصیلی معتبر نیست.",
        IssueCode.ACADEMIC_YEAR_RANGE: "اختلاف سال شروع و پایان باید ۱ باشد.",
    }
    return messages.get(code, code)
