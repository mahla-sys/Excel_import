"""Account self-service endpoints (change password)."""
from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import AuditAction, record_audit


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        return value


class ChangePasswordView(APIView):
    """
    Change the logged-in user's password. Clears the
    ``must_change_password`` flag on success. The current password must be
    supplied to prove possession.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(ser.validated_data["current_password"]):
            raise serializers.ValidationError(
                {"current_password": ["رمز فعلی صحیح نیست."]}
            )

        user.set_password(ser.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        record_audit(
            actor=user,
            action=AuditAction.PASSWORD_CHANGE,
            entity_type="PortalUser",
            entity_id=user.id,
            request=request,
        )

        # Rotate the session so the old password cookie no longer works.
        from django.contrib.auth import login, update_session_auth_hash
        update_session_auth_hash(request, user)
        return Response({"must_change_password": False}, status=status.HTTP_200_OK)
