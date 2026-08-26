from django.contrib import admin

from .models import ImportBatch, MappingProfile


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "school", "academic_year_label", "status",
                    "original_filename", "uploaded_by", "uploaded_at")
    list_filter = ("status", "school")
    search_fields = ("original_filename", "academic_year_label", "file_hash")
    readonly_fields = [f.name for f in ImportBatch._meta.fields]
    exclude = ()

    def has_add_permission(self, request):
        return False


@admin.register(MappingProfile)
class MappingProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "version", "is_active", "updated_at")
    list_filter = ("is_active", "school")
    search_fields = ("name",)
