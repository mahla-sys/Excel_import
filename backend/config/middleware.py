"""
CSRF protection for JWT-cookie authentication (double-submit pattern).

The access token (HttpOnly cookie) carries a ``csrf`` claim. The SPA also
receives that same value in a *readable* cookie and must echo it back in the
``X-CSRFToken`` header on every state-changing request.

This middleware runs before DRF's authentication, so it decodes the token
cookie itself (signature is still verified by ``CookieJWTAuthentication``
when the view processes; here we only read the claim to compare it against
the header). This prevents cross-site state-changing requests even if the
victim's browser automatically attaches the HttpOnly cookies.

Read-only methods and the login endpoint itself are exempt.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import JsonResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PATHS = (
    "/api/v1/auth/login/",
    "/api/v1/auth/refresh/",
    "/api/v1/auth/csrf/",
)

logger = logging.getLogger("apps.security")


def _extract_csrf_claim(request) -> str | None:
    """Read the ``csrf`` claim from the access-token cookie without verifying."""
    token = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
    if not token:
        return None
    try:
        # We only need the payload claim here; signature/expiry are verified
        # later by DRF's authentication. Use ``options`` to avoid requiring
        # verification at this layer.
        from jwt import decode as jwt_decode

        payload = jwt_decode(
            token,
            options={"verify_signature": False, "verify_exp": True},
        )
        return payload.get("csrf")
    except Exception:
        # Expired/malformed token -> DRF will reject it with 401, but for
        # CSRF purposes there is no claim to compare, so we treat it as
        # "no token presented" and let the view decide.
        return None


class CsrfProtectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in SAFE_METHODS:
            return self.get_response(request)

        path = request.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PATHS):
            return self.get_response(request)

        expected = _extract_csrf_claim(request)
        if expected is None:
            # No JWT access cookie -> session auth or anonymous. Django's
            # own CSRF machinery handles session-based requests; anonymous
            # state-changing requests are rejected by view permissions.
            return self.get_response(request)

        provided = request.headers.get("X-CSRFToken", "")
        if not provided or provided != expected:
            return JsonResponse(
                {"detail": "توکن CSRF نامعتبر یا مفقود است."},
                status=403,
            )

        # Expose for downstream consumers / DRF authenticator.
        request.csrf_token = expected
        return self.get_response(request)
