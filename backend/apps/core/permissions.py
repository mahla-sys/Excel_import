from rest_framework import permissions


class IsSystemAdmin(permissions.BasePermission):
    """Only ``system_admin`` users (Django superusers are implied)."""

    message = "دسترسی فقط برای مدیر فنی مجاز است."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or getattr(user, "role", None) == "system_admin")
        )


class IsSchoolOperator(permissions.BasePermission):
    """Authenticated school operators (and admins for support)."""

    message = "دسترسی فقط برای مسئول مدرسه مجاز است."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.is_superuser or getattr(user, "role", None) in {
            "system_admin",
            "school_operator",
        }


def current_school(user):
    """
    Return the school tenant for the logged-in user.

    Operators are strictly bound to a single school; ``school_id`` is never
    accepted from request input for them.
    """
    if user.is_authenticated:
        return getattr(user, "school_tenant", None)
    return None


class SchoolScopedQuerySetMixin:
    """
    Filter querysets so operators only see their own school.

    For models that don't directly have a ``school`` field, override
    ``scope_to_school`` (e.g. ``student__batch__school``).
    """

    school_field = "school"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        if user.is_superuser or getattr(user, "role", None) == "system_admin":
            return qs

        school = current_school(user)
        if school is None:
            return qs.none()
        return qs.filter(**{self.school_field: school})
