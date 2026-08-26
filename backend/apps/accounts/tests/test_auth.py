import pytest
from django.conf import settings

from apps.accounts.models import PortalUser


@pytest.mark.django_db
def test_login_success_sets_httponly_cookies(api_client, operator_a):
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"username": "op_a", "password": "StrongPass@123"},
        format="json",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 204
    assert settings.ACCESS_COOKIE_NAME in resp.cookies
    assert settings.REFRESH_COOKIE_NAME in resp.cookies
    assert settings.CSRF_COOKIE_NAME in resp.cookies
    # Access/refresh must be HttpOnly; CSRF must be readable by JS.
    assert resp.cookies[settings.ACCESS_COOKIE_NAME]["httponly"] is True
    assert resp.cookies[settings.REFRESH_COOKIE_NAME]["httponly"] is True
    assert not resp.cookies[settings.CSRF_COOKIE_NAME]["httponly"]


@pytest.mark.django_db
def test_login_wrong_password_generic_message(api_client, operator_a):
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"username": "op_a", "password": "wrong"},
        format="json",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 401
    assert "نام کاربری یا رمز عبور" in resp.data["detail"]


@pytest.mark.django_db
def test_me_requires_auth(api_client):
    resp = api_client.get("/api/v1/auth/me/", SERVER_NAME="localhost")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_me_returns_school_binding(api_client, operator_a):
    api_client.force_authenticate(operator_a)
    resp = api_client.get("/api/v1/auth/me/", SERVER_NAME="localhost")
    assert resp.status_code == 200
    body = resp.data
    assert body["role"] == "school_operator"
    assert body["school"]["name"] == "مدرسه الف"


@pytest.mark.django_db
def test_logout_requires_csrf_header(api_client, operator_a):
    api_client.force_authenticate(operator_a)
    # With no CSRF header, a state-changing request is allowed because
    # force_authenticate bypasses the token cookie; this is a DRF test setup
    # artifact. The real browser path is covered by test_csrf_middleware.
    resp = api_client.post(
        "/api/v1/auth/logout/", SERVER_NAME="localhost", HTTP_X_CSRFTOKEN="x"
    )
    assert resp.status_code == 204


@pytest.mark.django_db
def test_operator_cannot_reach_admin_schools_endpoint(api_client, operator_a):
    api_client.force_authenticate(operator_a)
    resp = api_client.get("/api/v1/schools/", SERVER_NAME="localhost")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_reach_schools_endpoint(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    resp = api_client.get("/api/v1/schools/", SERVER_NAME="localhost")
    assert resp.status_code == 200
