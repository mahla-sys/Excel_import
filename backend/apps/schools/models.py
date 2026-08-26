from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel


class SchoolTenant(TimeStampedModel):
    """
    An independent school record in *this* portal.

    This is NOT a copy of the main system's School model; ``external_code``
    is a stable identifier that a future connector can use to map it to the
    corresponding school in the main system.
    """

    name = models.CharField(max_length=200)
    external_code = models.CharField(
        max_length=64,
        unique=True,
        help_text="کد پایدار برای تطبیق آینده با سیستم اصلی.",
    )
    is_active = models.BooleanField(default=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
