from django.contrib import admin

from .models import SchoolTenant


@admin.register(SchoolTenant)
class SchoolTenantAdmin(admin.ModelAdmin):
    list_display = ("name", "external_code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "external_code")
