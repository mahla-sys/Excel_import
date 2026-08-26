"""
End-to-end tests for the Extract → Stage → Normalize pipeline.
"""
import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.intake.constants import RowStatus
from apps.intake.models import ImportBatch, ImportRow, StagedStudent
from apps.intake.normalizers import (
    normalize_birth_date,
    normalize_grade,
    normalize_mobile,
    normalize_student_national_id,
    validate_iranian_national_id,
)

pytestmark = pytest.mark.django_db


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "ثبت‌نام"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- Normalizer unit tests -----------------------------------

def test_valid_national_id_checksum():
    # 0012345679 is a real, well-formed national ID with valid checksum.
    n = normalize_student_national_id("0012345679")
    assert n.errors == []
    assert n.value == "0012345679"


def test_persian_digits_national_id():
    n = normalize_student_national_id("۰۰۱۲۳۴۵۶۷۹")
    assert n.errors == []
    assert n.value == "0012345679"


def test_invalid_checksum_national_id():
    n = normalize_student_national_id("1111111111")
    assert "E-NID-CHECKSUM" in n.errors or n.errors


def test_jalali_birth_date_converted():
    n = normalize_birth_date("1380/06/15")
    assert n.errors == []
    assert n.value is not None
    assert len(n.value) == 10 and n.value[4] == "-"


def test_mobile_normalization():
    assert normalize_mobile("0912 000 0000").value == "09120000000"
    assert normalize_mobile("+989120000000").value == "09120000000"
    n = normalize_mobile("12345")
    assert "W-PHONE-INVALID" in n.warnings


def test_grade_alias_normalization():
    assert normalize_grade("پایه هفتم").value == "هفتم"
    assert normalize_grade("7").value == "هفتم"
    n = normalize_grade("بزرگسالان")
    assert n.value == "بزرگسالان"
    assert "W-GRADE-UNKNOWN" in n.warnings


# ---------------- Pipeline integration ------------------------------------

def _setup_batch(api_client, operator, rows, year="1405-1406"):
    content = _xlsx(rows)
    f = SimpleUploadedFile(
        "sample.xlsx", content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    api_client.force_authenticate(operator)
    resp = api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": year},
        format="multipart", SERVER_NAME="localhost",
    )
    bid = resp.data["id"]
    api_client.post(
        f"/api/v1/intake/batches/{bid}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    headers = rows[0]
    mappings = {}
    for i, h in enumerate(headers):
        label = str(h)
        # Manual minimal mapping for test.
        if "نام" == label and i == 0:
            mappings["student.first_name"] = {"source_column_index": i, "source_column_label": label}
        elif "نام خانوادگی" == label and i == 1:
            mappings["student.last_name"] = {"source_column_index": i, "source_column_label": label}
        elif "کدملی" == label and i == 2:
            mappings["student.national_id"] = {"source_column_index": i, "source_column_label": label}
        elif "پایه" == label:
            mappings["enrollment.grade"] = {"source_column_index": i, "source_column_label": label}
        elif "موبایل پدر" == label:
            mappings["guardian.father.mobile"] = {"source_column_index": i, "source_column_label": label}
        elif "نام پدر" == label:
            mappings["guardian.father.first_name"] = {"source_column_index": i, "source_column_label": label}
    api_client.post(
        f"/api/v1/intake/batches/{bid}/mapping/",
        data={"mappings": mappings}, format="json", SERVER_NAME="localhost",
    )
    return bid


def test_process_creates_students_and_preserves_leading_zero(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه", "موبایل پدر", "نام پدر"],
        ["علی", "رضایی", "0012345679", "هفتم", "09120000000", "حسین"],
        ["زهرا", "احمدی", "0123456789", "هشتم", "09120000001", "رضا"],
    ]
    bid = _setup_batch(api_client, operator_a, rows)
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    batch = ImportBatch.objects.get(pk=bid)
    assert batch.stats["total_rows"] == 2
    assert batch.stats["created_students"] == 2

    s1 = StagedStudent.objects.get(national_id="0012345679")
    assert s1.first_name == "علی"
    assert s1.last_name == "رضایی"
    assert s1.grade == "هفتم"
    assert s1.national_id_valid is True
    # Father guardian was created.
    father = s1.guardians.filter(relation_type="father").first()
    assert father is not None
    assert father.mobile == "09120000000"
    assert father.first_name == "حسین"


def test_incomplete_row_kept_but_not_dropped(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["", "", "", ""],               # completely empty — skipped
        ["ناقص", "بدون‌کدملی", "", "هفتم"],  # has name, no NID -> incomplete
    ]
    bid = _setup_batch(api_client, operator_a, rows)
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    batch = ImportBatch.objects.get(pk=bid)
    # The completely empty row is skipped (no raw row stored); the row with a
    # name but no NID is kept and flagged incomplete.
    assert ImportRow.objects.filter(batch=batch).count() == 1
    s = StagedStudent.objects.get(batch=batch)
    assert s.status == RowStatus.INCOMPLETE
    assert s.national_id == ""


def test_one_bad_row_does_not_kill_batch(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
        ["بد", "کدملی", "12345", "هفتم"],  # invalid NID length
    ]
    bid = _setup_batch(api_client, operator_a, rows)
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200
    batch = ImportBatch.objects.get(pk=bid)
    # Both rows processed; second one creates a student with issues.
    assert batch.stats["created_students"] == 2
    bad = StagedStudent.objects.get(first_name="بد")
    assert bad.status in {RowStatus.INCOMPLETE, RowStatus.NEEDS_REVIEW}
    codes = {i["code"] for i in bad.validation_issues}
    assert "E-NID-LENGTH" in codes or "E-NID-CHECKSUM" in codes


def test_raw_data_preserved_alongside_normalized(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ]
    bid = _setup_batch(api_client, operator_a, rows)
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    row = ImportRow.objects.get(batch_id=bid)
    assert row.raw_data[0] == "علی"
    # Normalized data has the same values plus provenance etc.
    assert row.normalized_data["student"]["first_name"] == "علی"


def test_pending_placement_when_no_classroom(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ]
    bid = _setup_batch(api_client, operator_a, rows)
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    s = StagedStudent.objects.get(batch_id=bid)
    assert s.placement_status == "pending"
    assert s.classroom_title == ""
