"""Shared serializer helpers."""
from rest_framework import serializers


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    """A model serializer that blocks all writes by default."""

    def create(self, validated_data):
        raise RuntimeError("This serializer is read-only.")

    def update(self, instance, validated_data):
        raise RuntimeError("This serializer is read-only.")
