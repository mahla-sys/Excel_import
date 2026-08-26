import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.intake.constants import BatchStatus
from apps.intake.models import ImportBatch
from apps.intake.tests.factories import sample_enrollment_xlsx

from apps.accounts.models import PortalUser


pytestmark = pytest.mark.django_db


def _upload(client, user, content: bytes, filename="sample.xlsx", year="1405-1406"):
    f = SimpleUploadedFile(filename, content,
                           content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    client.force_authenticate(user=user)
    return client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": year},
        format="multipart",
        SERVER_NAME="localhost",
    )


def test_operator_can_upload_xlsx(api_client, operator_a):
    resp = _upload(api_client, operator_a, sample_enrollment_xlsx())
    assert resp.status_code == 201, resp.data
    batch = ImportBatch.objects.get(pk=resp.data["id"])
    assert batch.school_id == operator_a.school_tenant_id
    assert batch.status == BatchStatus.UPLOADED
    assert batch.academic_year_label == "1405-1406"
    assert len(batch.workbook_sheets) == 1
    assert batch.workbook_sheets[0]["name"] == "ثبت‌نام"
    assert batch.selected_sheet == "ثبت‌نام"  # auto-selected single sheet
    # File is stored with a UUID name; original name is metadata only.
    assert batch.private_storage_path.endswith(".xlsx")
    assert "sample" not in batch.private_storage_path


def test_school_b_isolation_blocks_operator_a(api_client, operator_a, operator_b):
    """Operator A must never see B's batch."""
    resp = _upload(api_client, operator_b, sample_enrollment_xlsx())
    b_batch_id = resp.data["id"]
    # Switch to operator A.
    api_client.force_authenticate(operator_a)
    resp = api_client.get(f"/api/v1/intake/batches/{b_batch_id}/", SERVER_NAME="localhost")
    assert resp.status_code == 404
    # And the list endpoint doesn't include it either.
    listing = api_client.get("/api/v1/intake/batches/", SERVER_NAME="localhost").data
    ids = [b["id"] for b in listing["results"]] if "results" in listing else [b["id"] for b in listing]
    assert b_batch_id not in ids


def test_non_xlsx_rejected(api_client, operator_a):
    resp = _upload(api_client, operator_a, b"not a zip", filename="data.txt")
    assert resp.status_code == 400
    assert "file" in resp.data or "detail" in resp.data


def test_wrong_extension_rejected(api_client, operator_a):
    # .xls (legacy binary) is rejected in MVP.
    resp = _upload(api_client, operator_a, b"PK\x03\x04fake", filename="data.xls")
    assert resp.status_code == 400


def test_academic_year_required_in_correct_format(api_client, operator_a):
    f = SimpleUploadedFile("s.xlsx", sample_enrollment_xlsx(),
                           content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": "1404"},
        format="multipart",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 400
    assert "academic_year_label" in resp.data


def test_select_sheet_and_header_inspects_columns(api_client, operator_a):
    resp = _upload(api_client, operator_a, sample_enrollment_xlsx())
    batch_id = resp.data["id"]
    api_client.force_authenticate(operator_a)

    # Single sheet was auto-selected; select header row 1.
    resp = api_client.post(
        f"/api/v1/intake/batches/{batch_id}/select-header/",
        data={"header_row": 1},
        format="json",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    columns = resp.data["detected_columns"]
    labels = [c["label"] for c in columns]
    # Duplicate headers are preserved with positional identity (same label,
    # different indexes):
    assert labels.count("کدملی") == 3
    indexes = [c["index"] for c in columns if c["label"] == "کدملی"]
    assert indexes == [2, 6, 8]
    # Samples are captured for the operator's mapping decision.
    nid_col = columns[2]
    assert nid_col["samples"]  # at least one sample value
    assert nid_col["samples"][0] == "0012345679"  # leading zero preserved


def test_invalid_sheet_is_rejected(api_client, operator_a):
    resp = _upload(api_client, operator_a, sample_enrollment_xlsx())
    batch_id = resp.data["id"]
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        f"/api/v1/intake/batches/{batch_id}/select-sheet/",
        data={"sheet_name": "nonexistent"},
        format="json",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 400


def test_original_file_download_is_tenant_scoped(api_client, operator_a, operator_b):
    resp = _upload(api_client, operator_a, sample_enrollment_xlsx())
    batch_id = resp.data["id"]

    # Owner can download.
    api_client.force_authenticate(operator_a)
    resp = api_client.get(
        f"/api/v1/intake/batches/{batch_id}/original-file/",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp["Content-Disposition"]

    # Other school cannot.
    api_client.force_authenticate(operator_b)
    resp = api_client.get(
        f"/api/v1/intake/batches/{batch_id}/original-file/",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 404
