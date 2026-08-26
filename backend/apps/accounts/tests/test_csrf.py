"""
CSRF middleware integration tests using a real login (cookie-based).

The key invariant: a state-changing request without a valid X-CSRFToken
header must be rejected even when the victim's browser would auto-attach
the HttpOnly auth cookies.
"""
import pytest


@pytest.mark.django_db
def test_post_without_csrf_header_is_rejected(api_client, operator_a):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"username": "op_a", "password": "StrongPass@123"},
        format="json",
        SERVER_NAME="localhost",
    )
    assert login.status_code == 204
    # APIClient persists cookies across requests, simulating a browser.
    resp = api_client.post("/api/v1/auth/logout/", SERVER_NAME="localhost")
    assert resp.status_code == 403
    body = resp.json()
    assert "CSRF" in body["detail"]


@pytest.mark.django_db
def test_post_with_csrf_header_succeeds(api_client, operator_a):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"username": "op_a", "password": "StrongPass@123"},
        format="json",
        SERVER_NAME="localhost",
    )
    csrf = login.cookies["csrf_token"].value
    resp = api_client.post(
        "/api/v1/auth/logout/",
        HTTP_X_CSRFTOKEN=csrf,
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 204
