"""Serializers for the manual duplicate-review workflow."""
from rest_framework import serializers

from .models import DuplicateResolution, IDENTITY_ISSUE_CODES


class DuplicateResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DuplicateResolution
        fields = [
            "id", "student", "issue_code", "decision", "review_note",
            "reviewer", "reviewer_username", "other_student_ids", "created_at",
        ]
        read_only_fields = [
            "id", "student", "reviewer", "reviewer_username",
            "other_student_ids", "created_at",
        ]

    issue_code = serializers.ChoiceField(choices=[(c, c) for c in IDENTITY_ISSUE_CODES])
    review_note = serializers.CharField(min_length=3, max_length=2000)

    def validate_issue_code(self, value):
        # The code must actually exist on the student's current issues.
        student = self.context["student"]
        current = {i.get("code") for i in (student.validation_issues or [])}
        if value not in current:
            raise serializers.ValidationError(
                "این کد خطا در حال حاضر روی پرونده وجود ندارد."
            )
        return value
