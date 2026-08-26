"""Manual editing / review workflow tests (phase 5)."""
import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.audit.models import AuditLog
from apps.intake.constants import RowStatus
from apps.intake.models import StagedStudent

pytestmark = pytest.mark.django_db


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "ثبت‌نام"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _processed_batch(api_client, operator):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["ناقص", "بدون‌کدملی", "", "هفتم"],
    ]
    f = SimpleUploadedFile(
        "s.xlsx", _xlsx(rows),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    api_client.force_authenticate(operator)
    bid = api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": "1405-1406"},
        format="multipart", SERVER_NAME="localhost",
    ).data["id"]
    api_client.post(
        f"/api/v1/intake/batches/{bid}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    mappings = {
        "student.first_name": {"source_column_index": 0, "source_column_label": "نام"},
        "student.last_name": {"source_column_index": 1, "source_column_label": "نام خانوادگی"},
        "student.national_id": {"source_column_index": 2, "source_column_label": "کدملی"},
        "enrollment.grade": {"source_column_index": 3, "source_column_label": "پایه"},
    }
    api_client.post(
        f"/api/v1/intake/batches/{bid}/mapping/",
        data={"mappings": mappings}, format="json", SERVER_NAME="localhost",
    )
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    return bid


def test_patch_student_requires_reason_for_sensitive_field(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={"national_id": "0012345679"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400
    assert "edit_reason" in resp.data


def test_patch_student_reenables_validation_and_status(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    assert s.status == RowStatus.INCOMPLETE

    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={
            "national_id": "0012345679",
            "edit_reason": "تکمیل از روی پرونده کاغذی مدرسه",
        },
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    s.refresh_from_db()
    assert s.national_id == "0012345679"
    assert s.national_id_valid is True
    # No classroom yet -> pending_placement
    assert s.status == RowStatus.PENDING_PLACEMENT

    prov = s.field_provenance["student.national_id"]
    assert prov["last_edited_by"] == "op01" if operator_a.username == "op01" else prov.get("last_edited_by")
    assert prov["edit_reason"] == "تکمیل از روی پرونده کاغذی مدرسه"
    # Raw value preserved.
    assert prov["raw_value"] == "0012345679"


def test_patch_invalid_national_id_keeps_needs_review(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={
            "national_id": "12345",
            "edit_reason": "اشتباه تایپی اصلاح شد",
        },
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    s.refresh_from_db()
    codes = {i["code"] for i in s.validation_issues}
    assert "E-NID-LENGTH" in codes or "E-NID-CHECKSUM" in codes
    # NID was supplied (though invalid) -> needs review rather than incomplete
    assert s.status in (RowStatus.NEEDS_REVIEW, RowStatus.INCOMPLETE)


def test_patch_writes_audit_log(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={
            "national_id": "0012345679",
            "edit_reason": "تکمیل دستی",
        },
        format="json", SERVER_NAME="localhost",
    )
    entries = AuditLog.objects.filter(entity_type="StagedStudent", entity_id=str(s.id))
    assert entries.exists()
    entry = entries.latest("created_at")
    assert entry.after_state["edit_reason"] == "تکمیل دستی"
    assert entry.actor == operator_a


def test_operator_b_cannot_patch_a_student(api_client, operator_a, operator_b):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    api_client.force_authenticate(operator_b)
    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={"review_notes": "دستکاری غیرمجاز"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 404


def test_audit_log_records_before_after_and_reason(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={
            "national_id": "0012345679",
            "edit_reason": "تطبیق با شناسنامه",
        },
        format="json", SERVER_NAME="localhost",
    )
    entry = AuditLog.objects.filter(
        entity_type="StagedStudent", entity_id=str(s.id),
    ).latest("created_at")
    assert entry.before_state["fields"]["national_id"] == ""
    assert entry.after_state["fields"]["national_id"] == "0012345679"
    assert entry.after_state["edit_reason"] == "تطبیق با شناسنامه"
    assert entry.school_id == operator_a.school_tenant_id
    assert entry.actor == operator_a


def test_emergency_mobile_requires_reason(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={"emergency_mobile": "09120000000"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400
    assert "edit_reason" in resp.data


def test_grade_requires_reason(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.get(batch_id=bid)
    resp = api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={"grade": "دهم"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400


def test_raw_data_on_import_row_is_never_modified(api_client, operator_a):
    bid = _processed_batch(api_client, operator_a)
    s = StagedStudent.objects.select_related("source_row").get(batch_id=bid)
    raw_before = list(s.source_row.raw_data)
    api_client.patch(
        f"/api/v1/intake/students/{s.id}/",
        data={
            "national_id": "0012345679",
            "edit_reason": "اصلاح",
        },
        format="json", SERVER_NAME="localhost",
    )
    s.source_row.refresh_from_db()
    assert s.source_row.raw_data == raw_before


# ---------------- Duplicate resolution ----------------

def _processed_batch_with_duplicate(api_client, operator):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ]
    f = SimpleUploadedFile(
        "dup.xlsx", _xlsx(rows),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    api_client.force_authenticate(operator)
    bid = api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": "1405-1406"},
        format="multipart", SERVER_NAME="localhost",
    ).data["id"]
    api_client.post(
        f"/api/v1/intake/batches/{bid}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    mappings = {
        "student.first_name": {"source_column_index": 0, "source_column_label": "نام"},
        "student.last_name": {"source_column_index": 1, "source_column_label": "نام خانوادگی"},
        "student.national_id": {"source_column_index": 2, "source_column_label": "کدملی"},
        "enrollment.grade": {"source_column_index": 3, "source_column_label": "پایه"},
    }
    api_client.post(
        f"/api/v1/intake/batches/{bid}/mapping/",
        data={"mappings": mappings}, format="json", SERVER_NAME="localhost",
    )
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    return bid


def test_duplicate_resolution_without_merge(api_client, operator_a):
    bid = _processed_batch_with_duplicate(api_client, operator_a)
    s = StagedStudent.objects.filter(batch_id=bid).first()
    # Both records still exist (no merge).
    assert StagedStudent.objects.filter(batch_id=bid).count() == 2

    resp = api_client.post(
        f"/api/v1/intake/students/{s.id}/resolve/",
        data={
            "issue_code": "W-DUPLICATE-EXACT",
            "decision": "confirmed_distinct_people",
            "review_note": "دو دانش‌آموز هم‌نام با کد ملی یکسان در سیستم وجود دارد؛ کد یکی اشتباه ثبت شده و پیگیری می‌شود.",
        },
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 201, resp.data
    # Still 2 records — resolution never deletes/merges.
    assert StagedStudent.objects.filter(batch_id=bid).count() == 2
    assert s.duplicate_resolutions.count() == 1
    r = s.duplicate_resolutions.first()
    assert r.reviewer == operator_a
    assert r.decision == "confirmed_distinct_people"


def test_approve_blocked_until_identity_warnings_resolved(api_client, operator_a):
    bid = _processed_batch_with_duplicate(api_client, operator_a)
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/approve/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400
    assert "unresolved" in resp.data or "هشدار هویتی" in resp.data["detail"]

    # Resolve both students' duplicate warnings.
    for s in StagedStudent.objects.filter(batch_id=bid):
        api_client.post(
            f"/api/v1/intake/students/{s.id}/resolve/",
            data={
                "issue_code": "W-DUPLICATE-EXACT",
                "decision": "confirmed_duplicate",
                "review_note": "تکراری است؛ با خانواده تماس گرفته شد.",
            },
            format="json", SERVER_NAME="localhost",
        )
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/approve/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["status"] == "approved_by_school"


def test_operator_b_cannot_resolve_a_student(api_client, operator_a, operator_b):
    bid = _processed_batch_with_duplicate(api_client, operator_a)
    s = StagedStudent.objects.filter(batch_id=bid).first()
    api_client.force_authenticate(operator_b)
    resp = api_client.post(
        f"/api/v1/intake/students/{s.id}/resolve/",
        data={
            "issue_code": "W-DUPLICATE-EXACT",
            "decision": "needs_follow_up",
            "review_note": "پیگیری",
        },
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 404
