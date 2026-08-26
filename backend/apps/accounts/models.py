from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class PortalUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, password, **extra):
        if not username:
            raise ValueError("Username is required.")
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra)

    def create_superuser(self, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", PortalUser.Role.ADMIN)
        extra.setdefault("school_tenant", None)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff and is_superuser True.")
        return self._create_user(username, password, **extra)


class PortalUser(AbstractUser):
    """
    Portal user.

    * ``system_admin`` owns/deploys the portal and can manage schools and
      operators. ``school_tenant`` is NULL for them.
    * ``school_operator`` is strictly bound to exactly one school and can
      only ever touch that school's data.
    """

    class Role(models.TextChoices):
        ADMIN = "system_admin", "مدیر فنی"
        OPERATOR = "school_operator", "مسئول مدرسه"

    # We keep Django's ``username`` as the login handle; no public sign-up.
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.OPERATOR,
    )
    school_tenant = models.ForeignKey(
        "schools.SchoolTenant",
        on_delete=models.PROTECT,
        related_name="operators",
        null=True,
        blank=True,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # When True, the user is forced to set a new password before using any
    # other part of the portal (e.g. after an admin creates the account
    # with a temporary password).
    must_change_password = models.BooleanField(default=False)

    objects = PortalUserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="operator_must_have_school",
                check=(
                    models.Q(role="system_admin")
                    | models.Q(school_tenant__isnull=False)
                ),
                violation_error_message=(
                    "کاربر مسئول مدرسه باید به یک مدرسه متصل باشد."
                ),
            ),
        ]

    def __str__(self) -> str:
        if self.school_tenant_id:
            return f"{self.username} ({self.school_tenant.name})"
        return self.username

    @property
    def is_school_operator(self) -> bool:
        return self.role == self.Role.OPERATOR

    @property
    def is_system_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    def save(self, *args, **kwargs):
        # System admins never belong to a single school.
        if self.is_superuser or self.role == self.Role.ADMIN:
            self.school_tenant = None
        super().save(*args, **kwargs)
