"""Tests for forced password change on first login."""
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_me_includes_must_change_flag(api_client, operator_a):
    api_client.force_authenticate(operator_a)
    resp = api_client.get("/api/v1/auth/me/", SERVER_NAME="localhost")
    assert resp.status_code == 200
    assert "must_change_password" in resp.data
    assert resp.data["must_change_password"] is False


def test_change_password_requires_current(api_client, operator_a):
    operator_a.set_password("OldPass@123")
    operator_a.save()
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "wrong", "new_password": "NewStrong@123"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400


def test_change_password_clears_flag(api_client, operator_a):
    operator_a.set_password("OldPass@123")
    operator_a.must_change_password = True
    operator_a.save()
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "OldPass@123", "new_password": "NewStrong@123"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    operator_a.refresh_from_db()
    assert operator_a.must_change_password is False
    assert operator_a.check_password("NewStrong@123") is True


def test_weak_new_password_rejected(api_client, operator_a):
    operator_a.set_password("OldPass@123")
    operator_a.save()
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "OldPass@123", "new_password": "123"},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 400


def test_new_operator_created_with_flag(api_client, admin_user, schools):
    school = schools()[0] if callable(schools) else schools
    # The operator fixture creates schools; reuse one via API.
    from apps.schools.models import SchoolTenant
    s = SchoolTenant.objects.first()
    api_client.force_authenticate(admin_user)
    resp = api_client.post(
        "/api/v1/admin/operators/",
        {"username": "op_temp", "password": "TempPass@123", "school_tenant": s.id},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 201, resp.data
    u = User.objects.get(username="op_temp")
    assert u.must_change_password is True
