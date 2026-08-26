"""
School-operator dashboard and system-admin management endpoints.
"""
from __future__ import annotations

from django.db.models import Count, Q
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PortalUser
from apps.audit.models import AuditLog
from apps.core.permissions import IsSchoolOperator, IsSystemAdmin
from apps.schools.models import SchoolTenant

from .constants import BatchStatus, RowStatus
from .models import ImportBatch, StagedStudent


class DashboardView(APIView):
    """Aggregated stats for the logged-in operator's school."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_school_operator:
            school = user.school_tenant
            batches = ImportBatch.objects.filter(school=school)
            students = StagedStudent.objects.filter(batch__school=school)
        else:
            school = None
            batches = ImportBatch.objects.all()
            students = StagedStudent.objects.all()

        batch_counts = {s: 0 for s, _ in BatchStatus.choices}
        for row in batches.values("status").annotate(n=Count("id")):
            batch_counts[row["status"]] = row["n"]

        student_counts = {s: 0 for s, _ in RowStatus.choices}
        for row in students.values("status").annotate(n=Count("id")):
            student_counts[row["status"]] = row["n"]

        recent = list(
            batches.order_by("-uploaded_at").values(
                "id", "original_filename", "academic_year_label",
                "status", "uploaded_at",
            )[:10]
        )

        return Response({
            "school": {
                "id": school.id,
                "name": school.name,
                "external_code": school.external_code,
            } if school else None,
            "totals": {
                "batches": batches.count(),
                "students": students.count(),
                "approved_batches": batch_counts.get(BatchStatus.APPROVED, 0),
            },
            "batch_status_counts": batch_counts,
            "student_status_counts": student_counts,
            "recent_batches": recent,
        })


# ---- System-admin: schools and operators -------------------------------

class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolTenant
        fields = ["id", "name", "external_code", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class OperatorSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school_tenant.name", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=10)

    class Meta:
        model = PortalUser
        fields = [
            "id", "username", "school_tenant", "school_name",
            "is_active", "last_login", "created_at", "password",
        ]
        read_only_fields = ["id", "last_login", "created_at"]

    def create(self, validated):
        password = validated.pop("password", None)
        user = PortalUser(**validated, role="school_operator")
        if password:
            user.set_password(password)
            # Admin supplied a (likely temporary) password — force a change
            # on first login so the operator picks a secret only they know.
            user.must_change_password = True
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated):
        password = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class SchoolListCreateView(APIView):
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        schools = SchoolTenant.objects.all().order_by("name")
        return Response(SchoolSerializer(schools, many=True).data)

    def post(self, request):
        ser = SchoolSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        school = ser.save()
        return Response(SchoolSerializer(school).data, status=201)


class SchoolDetailView(APIView):
    permission_classes = [IsSystemAdmin]

    def _get(self, pk):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(SchoolTenant, pk=pk)

    def patch(self, request, pk):
        school = self._get(pk)
        ser = SchoolSerializer(school, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class OperatorListCreateView(APIView):
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        qs = PortalUser.objects.filter(role="school_operator").select_related("school_tenant")
        school_id = request.query_params.get("school")
        if school_id:
            qs = qs.filter(school_tenant_id=school_id)
        return Response(OperatorSerializer(qs, many=True).data)

    def post(self, request):
        ser = OperatorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get("school_tenant"):
            raise serializers.ValidationError({"school_tenant": "الزامی است."})
        user = ser.save()
        return Response(OperatorSerializer(user).data, status=201)


class OperatorDetailView(APIView):
    permission_classes = [IsSystemAdmin]

    def _get(self, pk):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(PortalUser, pk=pk, role="school_operator")

    def patch(self, request, pk):
        user = self._get(pk)
        ser = OperatorSerializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ---- Audit log (admin-only) --------------------------------------------

class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default="")
    school_name = serializers.CharField(source="school.name", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor_username", "action", "entity_type", "entity_id",
            "school_name", "before_state", "after_state", "ip_address",
            "created_at",
        ]


class AuditLogView(APIView):
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        qs = AuditLog.objects.select_related("actor", "school").order_by("-created_at")
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        entity = request.query_params.get("entity_type")
        if entity:
            qs = qs.filter(entity_type=entity)
        school = request.query_params.get("school")
        if school:
            qs = qs.filter(school_id=school)
        qs = qs[:200]
        return Response(AuditLogSerializer(qs, many=True).data)
