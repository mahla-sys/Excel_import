from __future__ import annotations

import re

from django.db import transaction
from rest_framework import serializers

from apps.schools.models import SchoolTenant

from .constants import BatchStatus, CANONICAL_FIELDS
from .models import ImportBatch, MappingProfile

# Academic year like 1405-1406 (Persian or Latin digits).
_ACADEMIC_YEAR_RE = re.compile(r"^[0-9۰-۹]{4}\s*-\s*[0-9۰-۹]{4}$")


class MappingProfileSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = MappingProfile
        fields = [
            "id", "school", "school_name", "name", "version", "is_active",
            "source_file_hint", "sheet_name_hint", "header_row_hint",
            "mappings", "unknown_columns", "history",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "version", "history", "created_by",
                            "created_at", "updated_at", "school", "school_name"]


class BatchListSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    uploaded_by_username = serializers.CharField(source="uploaded_by.username",
                                                  read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            "id", "school", "school_name", "uploaded_by_username",
            "original_filename", "academic_year_label", "status", "status_display",
            "selected_sheet", "header_row_number", "file_size",
            "uploaded_at", "processed_at", "reviewed_at", "approved_at",
            "stats",
        ]
        read_only_fields = fields


class BatchUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    academic_year_label = serializers.CharField(max_length=20)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_academic_year_label(self, value):
        value = (value or "").strip()
        if not _ACADEMIC_YEAR_RE.match(value):
            raise serializers.ValidationError(
                "فرمت سال تحصیلی باید مانند 1405-1406 باشد."
            )
        return value

    def validate(self, attrs):
        # Deferred import to avoid a circular dependency at module load.
        from .excel import validate_uploaded_file, WorkbookInspectionError

        f = attrs["file"]
        try:
            size = validate_uploaded_file(f)
        except WorkbookInspectionError as exc:
            raise serializers.ValidationError({"file": exc.message})
        attrs["file_size"] = size
        return attrs


class BatchDetailSerializer(BatchListSerializer):
    workbook_sheets = serializers.JSONField(read_only=True)
    detected_columns = serializers.JSONField(read_only=True)
    mapping_snapshot = serializers.JSONField(read_only=True)
    mapping_profile = serializers.PrimaryKeyRelatedField(read_only=True)
    failure_reason = serializers.CharField(read_only=True)

    class Meta(BatchListSerializer.Meta):
        fields = BatchListSerializer.Meta.fields + [
            "workbook_sheets", "detected_columns",
            "mapping_profile", "mapping_snapshot", "failure_reason",
        ]


class SelectSheetSerializer(serializers.Serializer):
    sheet_name = serializers.CharField(max_length=200)


class SelectHeaderSerializer(serializers.Serializer):
    header_row = serializers.IntegerField(min_value=1, max_value=100)


class MappingActionSerializer(serializers.Serializer):
    """
    Payload for saving / applying a mapping to a Batch.

    ``mappings``: ``{ canonical_field: {source_column_index, source_column_label} }``
    ``unknown_columns``: ``[ {index, label, action: extra_attribute|ignored|requires_decision} ]``
    ``save_as_profile``: optional profile name; when provided, a reusable
    MappingProfile is created/versioned for the school.
    """

    mappings = serializers.DictField(child=serializers.DictField(), required=False, default=dict)
    unknown_columns = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    save_as_profile = serializers.CharField(required=False, allow_blank=True)
    profile_id = serializers.IntegerField(required=False)
    # When true and mappings is empty, store the auto-suggested mapping so
    # the operator can review and refine it.
    accept_suggestions = serializers.BooleanField(required=False, default=False)

    def validate_mappings(self, value):
        for canonical_field, target in value.items():
            if canonical_field not in CANONICAL_FIELDS:
                raise serializers.ValidationError(
                    f"فیلد استاندارد ناشناخته: {canonical_field}"
                )
            if "source_column_index" not in target:
                raise serializers.ValidationError(
                    f"ستون منبع برای {canonical_field} مشخص نشده است."
                )
        return value
