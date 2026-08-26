"""Tests for dashboard and system-admin endpoints (phase 7)."""
import pytest

pytestmark = pytest.mark.django_db


def test_operator_dashboard_scoped_to_school(api_client, operator_a, operator_b):
    api_client.force_authenticate(operator_a)
    resp = api_client.get("/api/v1/dashboard/", SERVER_NAME="localhost")
    assert resp.status_code == 200, resp.data
    assert resp.data["school"]["external_code"] == operator_a.school_tenant.external_code
    # System admin sees school=null but still gets aggregates.
    api_client.force_authenticate(operator_b)
    resp_b = api_client.get("/api/v1/dashboard/", SERVER_NAME="localhost")
    assert resp_b.status_code == 200


def test_operator_cannot_access_admin_endpoints(api_client, operator_a):
    api_client.force_authenticate(operator_a)
    for url in [
        "/api/v1/admin/schools/",
        "/api/v1/admin/operators/",
        "/api/v1/admin/audit-log/",
    ]:
        resp = api_client.get(url, SERVER_NAME="localhost")
        assert resp.status_code in (401, 403), f"{url} should be forbidden"


def test_admin_can_create_school_and_operator(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    resp = api_client.post(
        "/api/v1/admin/schools/",
        data={"name": "هنرستان نمونه", "external_code": "SAMPLE-01"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 201, resp.data
    school_id = resp.data["id"]
    resp = api_client.post(
        "/api/v1/admin/operators/",
        data={
            "username": "op_sample",
            "password": "StrongPass@123",
            "school_tenant": school_id,
        },
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["school_name"] == "هنرستان نمونه"


def test_audit_log_requires_admin(api_client, admin_user, operator_a):
    # Upload a file (which is audited).
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.intake.tests.factories import sample_enrollment_xlsx

    api_client.force_authenticate(operator_a)
    f = SimpleUploadedFile(
        "s.xlsx", sample_enrollment_xlsx(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": "1405-1406"},
        format="multipart", SERVER_NAME="localhost",
    )
    api_client.force_authenticate(admin_user)
    resp = api_client.get("/api/v1/admin/audit-log/", SERVER_NAME="localhost")
    assert resp.status_code == 200
    assert any(e.get("action") for e in resp.data)
