from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import PortalUser
from apps.audit.services import AuditAction, record_audit
from apps.core.permissions import IsSystemAdmin

from .models import SchoolTenant
from .serializers import OperatorSerializer, SchoolSerializer


class SchoolViewSet(viewsets.ModelViewSet):
    """
    Management endpoint for ``system_admin`` only.

    School operators never reach this viewset; their school is derived from
    the authenticated user.
    """

    queryset = SchoolTenant.objects.all().order_by("name")
    serializer_class = SchoolSerializer
    permission_classes = [IsSystemAdmin]

    def perform_create(self, serializer):
        school = serializer.save()
        record_audit(
            actor=self.request.user,
            action=AuditAction.SCHOOL_CREATE,
            entity_type="SchoolTenant",
            entity_id=school.id,
            after_state={"name": school.name, "external_code": school.external_code},
            request=self.request,
        )

    def perform_update(self, serializer):
        before = {"name": serializer.instance.name, "is_active": serializer.instance.is_active}
        school = serializer.save()
        record_audit(
            actor=self.request.user,
            action=AuditAction.SCHOOL_UPDATE,
            entity_type="SchoolTenant",
            entity_id=school.id,
            before_state=before,
            after_state={"name": school.name, "is_active": school.is_active},
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        school = self.get_object()
        school.is_active = False
        school.save(update_fields=["is_active", "updated_at"])
        record_audit(
            actor=request.user,
            action=AuditAction.SCHOOL_DEACTIVATE,
            entity_type="SchoolTenant",
            entity_id=school.id,
            request=request,
        )
        return Response(self.get_serializer(school).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        school = self.get_object()
        school.is_active = True
        school.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(school).data)


class OperatorViewSet(viewsets.ModelViewSet):
    """Manage school operator accounts (system_admin only)."""

    queryset = (
        PortalUser.objects.filter(role=PortalUser.Role.OPERATOR)
        .select_related("school_tenant")
        .order_by("-created_at")
    )
    serializer_class = OperatorSerializer
    permission_classes = [IsSystemAdmin]

    def perform_create(self, serializer):
        user = serializer.save()
        record_audit(
            actor=self.request.user,
            action=AuditAction.OPERATOR_CREATE,
            entity_type="PortalUser",
            entity_id=user.id,
            after_state={
                "username": user.username,
                "school_tenant_id": user.school_tenant_id,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        before = {
            "is_active": serializer.instance.is_active,
            "school_tenant_id": serializer.instance.school_tenant_id,
        }
        user = serializer.save()
        record_audit(
            actor=self.request.user,
            action=AuditAction.OPERATOR_UPDATE,
            entity_type="PortalUser",
            entity_id=user.id,
            before_state=before,
            after_state={
                "is_active": user.is_active,
                "school_tenant_id": user.school_tenant_id,
            },
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        record_audit(
            actor=request.user,
            action=AuditAction.OPERATOR_DEACTIVATE,
            entity_type="PortalUser",
            entity_id=user.id,
            request=request,
        )
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)
