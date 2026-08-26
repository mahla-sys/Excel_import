from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    USER_LOGIN = "user.login", "ورود کاربر"
    USER_LOGOUT = "user.logout", "خروج کاربر"
    PASSWORD_CHANGE = "user.password_change", "تغییر رمز عبور"

    SCHOOL_CREATE = "school.create", "ساخت مدرسه"
    SCHOOL_UPDATE = "school.update", "ویرایش مدرسه"
    SCHOOL_DEACTIVATE = "school.deactivate", "غیرفعال‌سازی مدرسه"
    OPERATOR_CREATE = "operator.create", "ساخت مسئول مدرسه"
    OPERATOR_UPDATE = "operator.update", "ویرایش مسئول مدرسه"
    OPERATOR_DEACTIVATE = "operator.deactivate", "غیرفعال‌سازی مسئول"

    BATCH_UPLOAD = "batch.upload", "آپلود فایل"
    BATCH_DOWNLOAD_RAW = "batch.download_raw", "دانلود فایل خام"
    BATCH_SELECT_SHEET = "batch.select_sheet", "انتخاب Sheet"
    BATCH_SELECT_HEADER = "batch.select_header", "انتخاب Header"
    BATCH_MAPPING_SAVE = "batch.mapping_save", "ذخیره Mapping"
    BATCH_PROCESS = "batch.process", "پردازش Batch"
    BATCH_APPROVE = "batch.approve", "تأیید نهایی مدرسه"
    BATCH_ARCHIVE = "batch.archive", "بایگانی Batch"
    EXPORT_ERRORS = "export.errors", "دانلود گزارش خطاها"
    EXPORT_CANONICAL = "export.canonical", "دانلود خروجی استاندارد"
    BATCH_STATUS_CHANGE = "batch.status_change", "تغییر وضعیت Batch"

    ROW_UPDATE = "row.update", "ویرایش سطر"
    STUDENT_UPDATE = "student.update", "ویرایش پرونده‌ی دانش‌آموز"
    STUDENT_STATUS_CHANGE = "student.status_change", "تغییر وضعیت دانش‌آموز"

    MAPPING_PROFILE_CREATE = "mapping_profile.create", "ساخت Mapping Profile"
    MAPPING_PROFILE_UPDATE = "mapping_profile.update", "ویرایش Mapping Profile"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    # Denormalized for records where the user is later deleted.
    actor_username = models.CharField(max_length=150, blank=True)
    school = models.ForeignKey(
        "schools.SchoolTenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=AuditAction.choices)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["school", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} by {self.actor_username}"
