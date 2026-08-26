from rest_framework import serializers

from apps.accounts.models import PortalUser

from .models import SchoolTenant


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolTenant
        fields = ["id", "name", "external_code", "is_active", "contact_name", "contact_phone"]
        read_only_fields = ["id"]


class OperatorSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school_tenant.name", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=10)

    class Meta:
        model = PortalUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "school_tenant",
            "school_name",
            "is_active",
            "last_login",
            "created_at",
            "password",
        ]
        read_only_fields = ["id", "role", "last_login", "created_at", "school_name"]

    def create(self, validated_data):
        school = validated_data.get("school_tenant")
        if school is None:
            raise serializers.ValidationError({"school_tenant": "انتخاب مدرسه الزامی است."})
        password = validated_data.pop("password", None)
        user = PortalUser(**validated_data, role=PortalUser.Role.OPERATOR)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Force role back to operator; only the model-level admin can change it.
        instance.role = PortalUser.Role.OPERATOR
        if password:
            instance.set_password(password)
        instance.save()
        return instance
