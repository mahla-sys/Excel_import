"""Validation / duplicate detection / approval workflow tests."""
import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.intake.constants import RowStatus
from apps.intake.models import StagedStudent
from apps.intake.validation import validate_batch

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


def _process_via_api(api_client, operator, rows):
    content = _xlsx(rows)
    f = SimpleUploadedFile(
        "sample.xlsx", content,
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
    headers = rows[0]
    mappings = {}
    for i, h in enumerate(headers):
        label = str(h)
        if i == 0: mappings["student.first_name"] = {"source_column_index": i, "source_column_label": label}
        elif i == 1: mappings["student.last_name"] = {"source_column_index": i, "source_column_label": label}
        elif i == 2: mappings["student.national_id"] = {"source_column_index": i, "source_column_label": label}
        elif i == 3: mappings["enrollment.grade"] = {"source_column_index": i, "source_column_label": label}
    api_client.post(
        f"/api/v1/intake/batches/{bid}/mapping/",
        data={"mappings": mappings}, format="json", SERVER_NAME="localhost",
    )
    api_client.post(
        f"/api/v1/intake/batches/{bid}/process/",
        format="json", SERVER_NAME="localhost",
    )
    return bid


def test_duplicate_national_id_flagged_within_batch(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
        ["علی", "رضایی", "0012345679", "هفتم"],  # same NID
    ]
    bid = _process_via_api(api_client, operator_a, rows)
    students = list(StagedStudent.objects.filter(batch_id=bid).order_by("id"))
    codes = [i["code"] for s in students for i in s.validation_issues]
    assert "W-DUPLICATE-EXACT" in codes
    # No auto-merge: two distinct staged students.
    assert len(students) == 2


def test_incomplete_blocks_approval(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["ناقص", "بدون‌کدملی", "", "هفتم"],
    ]
    bid = _process_via_api(api_client, operator_a, rows)
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/approve/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400
    s = StagedStudent.objects.get(batch_id=bid)
    assert s.status == RowStatus.INCOMPLETE


def test_valid_student_pending_placement(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ]
    bid = _process_via_api(api_client, operator_a, rows)
    s = StagedStudent.objects.get(batch_id=bid)
    # No classroom -> pending_placement.
    assert s.status == RowStatus.PENDING_PLACEMENT


def test_cross_batch_nid_match_flagged(api_client, operator_a):
    rows1 = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ]
    _process_via_api(api_client, operator_a, rows1)
    rows2 = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هشتم"],
    ]
    bid2 = _process_via_api(api_client, operator_a, rows2)
    s2 = StagedStudent.objects.get(batch_id=bid2)
    codes = [i["code"] for i in s2.validation_issues]
    assert "W-DUPLICATE-EXACT" in codes
    previous = [i for i in s2.validation_issues if i.get("previous_batch_id")]
    assert previous, "expected a cross-batch duplicate notice"


def test_approve_after_resolving_incomplete(api_client, operator_a):
    rows = [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["ناقص", "بدون‌کدملی", "", "هفتم"],
    ]
    bid = _process_via_api(api_client, operator_a, rows)
    s = StagedStudent.objects.get(batch_id=bid)
    s.national_id = "0012345679"
    s.national_id_valid = True
    s.save()
    # Re-run validation to refresh statuses.
    validate_batch(s.batch)
    s.refresh_from_db()
    assert s.status == RowStatus.PENDING_PLACEMENT
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/approve/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200
    assert resp.data["status"] == "approved_by_school"


def test_operator_b_cannot_approve_a_batch(api_client, operator_a, operator_b):
    bid = _process_via_api(api_client, operator_a, [
        ["نام", "نام خانوادگی", "کدملی", "پایه"],
        ["علی", "رضایی", "0012345679", "هفتم"],
    ])
    api_client.force_authenticate(operator_b)
    resp = api_client.post(
        f"/api/v1/intake/batches/{bid}/approve/",
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 404
