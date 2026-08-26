from rest_framework import serializers

from .models import PortalUser


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class MeSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    school = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = PortalUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "role_display",
            "school",
            "is_active",
            "last_login",
            "must_change_password",
        ]
        read_only_fields = fields

    def get_full_name(self, obj: PortalUser) -> str:
        return obj.get_full_name() or obj.username

    def get_school(self, obj: PortalUser):
        school = obj.school_tenant
        if school is None:
            return None
        return {
            "id": school.id,
            "name": school.name,
            "external_code": school.external_code,
        }
