"""JWT authentication that reads the access token from an HttpOnly cookie."""
from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


class CookieJWTAuthentication(BaseAuthentication):
    """
    Authenticate using the JWT access token stored in an HttpOnly cookie.

    The access token contains a ``csrf`` claim which is exposed on the
    request as ``request.csrf_token`` for ``CsrfProtectMiddleware`` to
    compare against the ``X-CSRFToken`` header (double-submit).
    """

    def authenticate(self, request):
        token = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
        if not token:
            return None

        try:
            validated = AccessToken(token)
        except TokenError as exc:
            raise AuthenticationFailed("توکن ورود نامعتبر یا منقضی شده است.") from exc

        from apps.accounts.models import PortalUser

        user_id = validated.get("user_id")
        if user_id is None:
            raise AuthenticationFailed("توکن فاقد شناسه کاربر است.")

        try:
            user = PortalUser.objects.select_related("school_tenant").get(
                id=user_id, is_active=True
            )
        except PortalUser.DoesNotExist as exc:
            raise AuthenticationFailed("کاربر یافت نشد یا غیرفعال است.") from exc

        # Expose the CSRF claim for the middleware.
        request.csrf_token = validated.get("csrf")
        return user, validated

    def authenticate_header(self, request):
        return "Cookie"
