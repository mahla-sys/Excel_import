from rest_framework import serializers

from .models import ImportRow, StagedGuardian, StagedStudent


class StagedGuardianSerializer(serializers.ModelSerializer):
    relation_display = serializers.CharField(source="get_relation_type_display", read_only=True)

    class Meta:
        model = StagedGuardian
        fields = [
            "id", "relation_type", "relation_display",
            "first_name", "last_name", "full_name", "national_id",
            "mobile", "occupation", "education_level",
        ]


class StagedStudentListSerializer(serializers.ModelSerializer):
    guardians = StagedGuardianSerializer(many=True, read_only=True)

    class Meta:
        model = StagedStudent
        fields = [
            "id", "first_name", "last_name", "full_name",
            "national_id", "national_id_valid", "source_student_code",
            "grade", "classroom_title", "placement_status",
            "admission_status", "gender", "status", "guardians",
            "validation_issues",
        ]


class StagedStudentDetailSerializer(StagedStudentListSerializer):
    duplicate_resolutions = serializers.SerializerMethodField()

    class Meta(StagedStudentListSerializer.Meta):
        fields = StagedStudentListSerializer.Meta.fields + [
            "birth_date", "birth_place",
            "contacts", "admission_data", "extra_attributes",
            "field_provenance", "validation_issues",
            "review_notes", "academic_year",
            "created_at", "updated_at",
            "duplicate_resolutions",
        ]

    def get_duplicate_resolutions(self, obj):
        return [
            {
                "id": r.id,
                "issue_code": r.issue_code,
                "decision": r.decision,
                "review_note": r.review_note,
                "reviewer_username": r.reviewer_username,
                "created_at": r.created_at,
            }
            for r in obj.duplicate_resolutions.all().order_by("-created_at")
        ]


class ImportRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRow
        fields = [
            "id", "row_number", "raw_data", "normalized_data",
            "validation_issues", "status", "staged_student",
        ]
