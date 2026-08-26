"""
Token issuance for cookie-based JWT auth.

An additional random ``csrf`` claim is embedded in the access token and
also sent in a *readable* cookie. The browser reads that cookie and echoes
it back in the ``X-CSRFToken`` header on state-changing requests; the
middleware compares the header value against the claim in the verified
token.
"""
from __future__ import annotations

import secrets
from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


def _build_tokens(user) -> tuple[str, str, str]:
    """Return (access_token, refresh_token, csrf_token) for ``user``."""
    refresh = RefreshToken.for_user(user)
    csrf_token = secrets.token_urlsafe(32)
    # Inject the CSRF token into both tokens so refresh also rotates it.
    refresh["csrf"] = csrf_token
    access: AccessToken = refresh.access_token
    access["csrf"] = csrf_token
    return str(access), str(refresh), csrf_token


def set_auth_cookies(
    response: Response, access: str, refresh: str, csrf_token: str
) -> Response:
    response.set_cookie(
        settings.ACCESS_COOKIE_NAME,
        access,
        max_age=int(settings.JWT_ACCESS_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        max_age=int(settings.JWT_REFRESH_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    # The CSRF cookie is intentionally readable by JS (double-submit pattern).
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=int(settings.JWT_REFRESH_LIFETIME.total_seconds()),
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return response


def clear_auth_cookies(response: Response) -> Response:
    for name in (
        settings.ACCESS_COOKIE_NAME,
        settings.REFRESH_COOKIE_NAME,
        settings.CSRF_COOKIE_NAME,
    ):
        response.delete_cookie(name, path="/", domain=settings.COOKIE_DOMAIN)
    return response


def issue_tokens_for_user(user) -> dict[str, Any]:
    """Issue fresh tokens and return a response payload (without tokens in body)."""
    access, refresh, csrf = _build_tokens(user)
    response = Response(status=status.HTTP_204_NO_CONTENT)
    set_auth_cookies(response, access, refresh, csrf)
    return response
