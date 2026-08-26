from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PortalUser


@admin.register(PortalUser)
class PortalUserAdmin(UserAdmin):
    list_display = ("username", "role", "school_tenant", "is_active", "last_login")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("پرتال", {"fields": ("role", "school_tenant", "phone_number")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("پرتال", {"fields": ("role", "school_tenant", "phone_number")}),
    )
