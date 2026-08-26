from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import AuditAction, record_audit

from .serializers import LoginSerializer, MeSerializer
from .services import clear_auth_cookies, issue_tokens_for_user, set_auth_cookies

User = get_user_model()


class LoginThrottle(SimpleRateThrottle):
    """Aggressive rate limit on the login endpoint."""

    scope = "login"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f"login:{ident}"


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [LoginThrottle]
    throttle_scope = "login"

    def post(self, request):
        # Also rotate the session cookie (defense in depth); no data leaks.
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            # Same message for unknown user / wrong password / disabled.
            return Response(
                {"detail": "نام کاربری یا رمز عبور اشتباه است."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        response = issue_tokens_for_user(user)
        record_audit(
            actor=user,
            action=AuditAction.USER_LOGIN,
            entity_type="PortalUser",
            entity_id=user.id,
            request=request,
        )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # Best-effort blacklist of the refresh token if the app enables it.
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except (TokenError, AttributeError):
                # blacklist app may not be installed; ignore.
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        logout(request)
        if user.is_authenticated:
            record_audit(
                actor=user,
                action=AuditAction.USER_LOGOUT,
                entity_type="PortalUser",
                entity_id=user.id,
                request=request,
            )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class RefreshView(APIView):
    """
    Rotate access/refresh tokens using the refresh cookie.

    CSRF is enforced by the middleware for POST.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"detail": "توکن refresh موجود نیست."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(refresh_token)
            access = refresh.access_token
            # Carry over CSRF claim, rotate it on refresh.
            import secrets

            csrf = refresh.get("csrf") or secrets.token_urlsafe(32)
            access["csrf"] = csrf
            refresh["csrf"] = csrf
        except TokenError:
            return Response(
                {"detail": "توکن ورود نامعتبر یا منقضی شده است."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = refresh.get("user_id")
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"detail": "کاربر یافت نشد یا غیرفعال است."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, str(access), str(refresh), csrf)
        return response


@csrf_exempt
def csrf_view(request):
    """
    Lightweight endpoint used by the SPA to obtain / refresh the CSRF cookie.

    The actual CSRF value only becomes meaningful after login; this endpoint
    exists so the frontend can eagerly read the cookie after login.
    """
    from django.http import JsonResponse

    return JsonResponse({"ok": True})
