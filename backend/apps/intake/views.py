from __future__ import annotations

import hashlib

from django.core.files import File
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import AuditAction, record_audit
from apps.core.permissions import IsSchoolOperator, SchoolScopedQuerySetMixin
from apps.schools.models import SchoolTenant

from .constants import BatchStatus, CANONICAL_FIELDS, RowStatus
from .excel import (
    WorkbookInspectionError,
    count_data_rows,
    inspect_columns,
    list_sheets,
)
from .mapping import ensure_no_duplicate_targets, suggest_mappings
from .models import ImportBatch, ImportRow, MappingProfile, StagedStudent
from .processor import process_batch
from .validation import validate_batch
from . import exports
from .serializers import (
    BatchDetailSerializer,
    BatchListSerializer,
    BatchUploadSerializer,
    MappingActionSerializer,
    MappingProfileSerializer,
    SelectHeaderSerializer,
    SelectSheetSerializer,
)
from .serializers_rows import StagedStudentDetailSerializer


def _resolve_school(request) -> SchoolTenant:
    """
    Return the school that should own the request's data.

    For operators the school is ALWAYS taken from their account. For
    system admins we allow an explicit ``school`` query/form param so they
    can act on any school via management endpoints.
    """
    user = request.user
    if user.is_school_operator:
        if not user.school_tenant_id or not user.school_tenant.is_active:
            raise ValidationError({"detail": "حساب شما به یک مدرسه‌ی فعال متصل نیست."})
        return user.school_tenant

    school_id = request.data.get("school") or request.query_params.get("school")
    if not school_id:
        raise ValidationError({"school": "انتخاب مدرسه برای مدیر فنی الزامی است."})
    try:
        return SchoolTenant.objects.get(pk=school_id, is_active=True)
    except SchoolTenant.DoesNotExist as exc:
        raise ValidationError({"school": "مدرسه انتخاب‌شده معتبر نیست."}) from exc


class ImportBatchViewSet(SchoolScopedQuerySetMixin, viewsets.ModelViewSet):
    """
    Intake batches for the logged-in operator's school.

    State-changing actions on a batch are audited. The raw file is only
    reachable through ``original-file`` which re-checks authorization.
    """

    permission_classes = [IsSchoolOperator]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = None
    # Base queryset; SchoolScopedQuerySetMixin.get_queryset() applies the
    # school filter for operators. This attribute MUST exist for the mixin.
    queryset = ImportBatch.objects.all()

    def get_queryset(self):
        # IMPORTANT: always go through SchoolScopedQuerySetMixin so operators
        # are confined to their own school. Never bypass with .all() here.
        qs = super().get_queryset()
        return qs.select_related("school", "uploaded_by", "mapping_profile")

    def get_serializer_class(self):
        if self.action == "list":
            return BatchListSerializer
        if self.action in ("retrieve", "partial_update"):
            return BatchDetailSerializer
        return BatchListSerializer

    # ------------------------------------------------------------------
    # Upload (POST /api/batches/upload/)
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request):
        serializer = BatchUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = _resolve_school(request)

        uploaded = serializer.validated_data["file"]
        academic_year = serializer.validated_data["academic_year_label"]
        notes = serializer.validated_data.get("notes", "")

        # Hash the file as it is read by openpyxl below; we hash once on a
        # fresh seek to keep it simple.
        uploaded.seek(0)
        file_hash = hashlib.sha256()
        for chunk in uploaded.chunks():
            file_hash.update(chunk)
        digest = file_hash.hexdigest()
        uploaded.seek(0)

        try:
            with transaction.atomic():
                batch = ImportBatch(
                    school=school,
                    uploaded_by=request.user,
                    original_filename=uploaded.name[:300],
                    file_hash=digest,
                    file_size=serializer.validated_data["file_size"],
                    academic_year_label=academic_year,
                    notes=notes,
                    status=BatchStatus.UPLOADED,
                )
                # Save the file into private storage with a UUID path.
                batch.save_private_file(uploaded, school.id)
                batch.save()

                # Discover sheets immediately so the UI can show the wizard.
                with batch.open_private_file() as f:
                    sheets = list_sheets(File(f))
                batch.workbook_sheets = [
                    {"name": s.name, "max_row": s.max_row, "max_column": s.max_column}
                    for s in sheets
                ]
                # If there is only one sheet, select it automatically but
                # leave header selection to the user.
                if len(sheets) == 1:
                    batch.selected_sheet = sheets[0].name
                batch.save(update_fields=["workbook_sheets", "selected_sheet", "updated_at"])

        except WorkbookInspectionError as exc:
            raise ValidationError({"file": exc.message})

        record_audit(
            actor=request.user,
            action=AuditAction.BATCH_UPLOAD,
            entity_type="ImportBatch",
            entity_id=batch.id,
            school=school,
            after_state={
                "filename": batch.original_filename,
                "size": batch.file_size,
                "sha256": digest,
            },
            request=request,
        )

        return Response(
            BatchDetailSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Sheet / header selection
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="select-sheet")
    def select_sheet(self, request, pk=None):
        batch = self.get_object()
        serializer = SelectSheetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sheet_name = serializer.validated_data["sheet_name"]

        valid_names = {s["name"] for s in batch.workbook_sheets}
        if sheet_name not in valid_names:
            raise ValidationError({"sheet_name": "برگه انتخاب‌شده در این فایل وجود ندارد."})

        batch.selected_sheet = sheet_name
        # Reset header & columns when sheet changes.
        batch.header_row_number = None
        batch.detected_columns = []
        batch.status = BatchStatus.MAPPING_REQUIRED
        batch.save(update_fields=[
            "selected_sheet", "header_row_number", "detected_columns",
            "status", "updated_at",
        ])

        record_audit(
            actor=request.user, action=AuditAction.BATCH_SELECT_SHEET,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            after_state={"selected_sheet": sheet_name}, request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="select-header")
    def select_header(self, request, pk=None):
        batch = self.get_object()
        if not batch.selected_sheet:
            raise ValidationError({"detail": "ابتدا یک برگه انتخاب کنید."})

        serializer = SelectHeaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        header_row = serializer.validated_data["header_row"]

        with batch.open_private_file() as f:
            columns = inspect_columns(File(f), batch.selected_sheet, header_row)

        batch.header_row_number = header_row
        batch.detected_columns = [
            {"index": c.index, "letter": c.letter, "label": c.label, "samples": c.samples}
            for c in columns
        ]
        batch.status = BatchStatus.MAPPING_REQUIRED
        batch.save(update_fields=[
            "header_row_number", "detected_columns", "status", "updated_at"
        ])

        record_audit(
            actor=request.user, action=AuditAction.BATCH_SELECT_HEADER,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            after_state={"header_row": header_row, "column_count": len(columns)},
            request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    # ------------------------------------------------------------------
    # Preview / save mapping (phase 2; persistence is here so the model
    # is ready when the extract/normalize engine lands in phase 3).
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Smart suggestions (phase 2)
    # ------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="mapping/suggestions")
    def mapping_suggestions(self, request, pk=None):
        batch = self.get_object()
        if not batch.detected_columns:
            raise ValidationError({"detail": "ابتدا ردیف هدر را انتخاب کنید."})
        suggestions = suggest_mappings(batch.detected_columns)
        payload = [
            {
                "column_index": s.column_index,
                "column_label": s.column_label,
                "target": s.target,
                "target_label": s.target_label,
                "confidence": s.confidence,
                "reason": s.reason,
                "alternatives": s.alternatives,
            }
            for s in suggestions
        ]
        return Response({"suggestions": payload})

    @action(detail=True, methods=["post"], url_path="mapping")
    def save_mapping(self, request, pk=None):
        batch = self.get_object()
        if not batch.detected_columns:
            raise ValidationError({"detail": "ابتدا ردیف هدر را انتخاب کنید."})

        serializer = MappingActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mappings = serializer.validated_data["mappings"]
        unknown = serializer.validated_data.get("unknown_columns", [])
        save_as = (serializer.validated_data.get("save_as_profile") or "").strip()
        profile_id = serializer.validated_data.get("profile_id")
        accept_suggestions = serializer.validated_data.get("accept_suggestions", False)

        # If operator asks to accept suggestions, seed the mapping from them.
        if accept_suggestions and not mappings:
            suggestions = suggest_mappings(batch.detected_columns)
            mappings = {}
            for s in suggestions:
                if s.target and s.confidence in {"high", "medium"}:
                    mappings[s.target] = {
                        "source_column_index": s.column_index,
                        "source_column_label": s.column_label,
                    }

        # Validate source column indexes against the detected columns.
        valid_indexes = {c["index"] for c in batch.detected_columns}
        for canonical, target in mappings.items():
            if target["source_column_index"] not in valid_indexes:
                raise ValidationError(
                    {"mappings": f"ستون منبع برای {canonical} نامعتبر است."}
                )

        # Warn (but don't block) when two canonical fields target one column.
        consistency_warnings = ensure_no_duplicate_targets(mappings)

        with transaction.atomic():
            profile = None
            if profile_id:
                try:
                    profile = MappingProfile.objects.get(
                        pk=profile_id, school=batch.school, is_active=True
                    )
                except MappingProfile.DoesNotExist as exc:
                    raise ValidationError({"profile_id": "پروفایل نگاشت معتبر نیست."}) from exc

            if save_as:
                # Create or update a reusable profile.
                profile = MappingProfile.objects.filter(
                    school=batch.school, name=save_as, is_active=True
                ).first()
                if profile:
                    # Append the previous snapshot to history and bump version.
                    history_entry = {
                        "version": profile.version,
                        "mappings": profile.mappings,
                        "unknown_columns": profile.unknown_columns,
                        "edited_by_id": request.user.id,
                        "edited_at": timezone.now().isoformat(),
                    }
                    profile.history = (profile.history or []) + [history_entry]
                    profile.version += 1
                    profile.mappings = mappings
                    profile.unknown_columns = unknown
                    profile.sheet_name_hint = batch.selected_sheet
                    profile.header_row_hint = batch.header_row_number
                    profile.edited_by = request.user
                    profile.save()
                else:
                    profile = MappingProfile.objects.create(
                        school=batch.school,
                        name=save_as,
                        mappings=mappings,
                        unknown_columns=unknown,
                        sheet_name_hint=batch.selected_sheet,
                        header_row_hint=batch.header_row_number,
                        created_by=request.user,
                    )

            batch.mapping_snapshot = {
                "mappings": mappings,
                "unknown_columns": unknown,
                "saved_at": timezone.now().isoformat(),
                "profile_id": profile.id if profile else None,
                "profile_version": profile.version if profile else None,
            }
            if profile is not None:
                batch.mapping_profile = profile
            batch.status = BatchStatus.MAPPING_REQUIRED
            batch.save(update_fields=[
                "mapping_snapshot", "mapping_profile", "status", "updated_at"
            ])

        record_audit(
            actor=request.user, action=AuditAction.BATCH_MAPPING_SAVE,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            after_state={
                "mapped_fields": sorted(mappings.keys()),
                "unknown_count": len(unknown),
                "profile_id": profile.id if profile else None,
                "consistency_warnings": consistency_warnings,
            },
            request=request,
        )
        data = BatchDetailSerializer(batch).data
        if consistency_warnings:
            data = dict(data)
            data["consistency_warnings"] = consistency_warnings
        return Response(data)

    @action(detail=True, methods=["get"], url_path="row-count")
    def row_count(self, request, pk=None):
        """Count data rows (for enforcing the 5,000-row MVP limit)."""
        batch = self.get_object()
        if not (batch.selected_sheet and batch.header_row_number):
            raise ValidationError({"detail": "ابتدا برگه و ردیف هدر را انتخاب کنید."})
        with batch.open_private_file() as f:
            count = count_data_rows(File(f), batch.selected_sheet, batch.header_row_number)
        return Response({"data_rows": count, "limit": 5000, "within_limit": count <= 5000})

    # ------------------------------------------------------------------
    # Secure raw-file download
    # ------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="original-file")
    def original_file(self, request, pk=None):
        batch = self.get_object()  # Scoped by SchoolScopedQuerySetMixin.

        # Stream the file from private storage. No public URL ever exists.
        try:
            f = batch.open_private_file()
        except FileNotFoundError as exc:
            raise Http404("فایل خام در دسترس نیست.") from exc

        # Force download; use the original filename in Content-Disposition
        # while escaping non-ASCII. The stored name is UUID-based and safe.
        from urllib.parse import quote

        ascii_fallback = "enrollment.xlsx"
        response = FileResponse(f, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = (
            f"attachment; filename=\"{ascii_fallback}\"; "
            f"filename*=UTF-8''{quote(batch.original_filename)}"
        )
        response["Content-Length"] = batch.file_size
        response["X-Content-Type-Options"] = "nosniff"

        record_audit(
            actor=request.user, action=AuditAction.BATCH_DOWNLOAD_RAW,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            request=request,
        )
        return response

    # ------------------------------------------------------------------
    # Processing (Extract → Stage → Normalize)
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        batch = self.get_object()
        if not batch.mapping_snapshot:
            raise ValidationError({"detail": "ابتدا نگاشت ستون‌ها را ذخیره کنید."})
        if not batch.is_editable and batch.status not in {
            BatchStatus.VALIDATED,
            BatchStatus.REVIEW_REQUIRED,
            BatchStatus.FAILED,
        }:
            raise ValidationError({"detail": "این Batch قابل پردازش مجدد نیست."})

        try:
            stats = process_batch(batch)
        except Exception as exc:
            raise ValidationError({"detail": f"پردازش ناموفق بود: {exc}"}) from exc

        record_audit(
            actor=request.user, action=AuditAction.BATCH_PROCESS,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            after_state=stats.to_dict(), request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="revalidate")
    def revalidate(self, request, pk=None):
        """Re-run cross-row validation without re-reading the Excel file."""
        batch = self.get_object()
        if not batch.staged_students.exists():
            raise ValidationError({"detail": "ابتدا Batch را پردازش کنید."})
        outcome = validate_batch(batch)
        record_audit(
            actor=request.user, action=AuditAction.BATCH_PROCESS,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            after_state={"revalidate": outcome.to_dict()}, request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        from .models import DuplicateResolution, IDENTITY_ISSUE_CODES

        batch = self.get_object()
        if not batch.staged_students.exists():
            raise ValidationError({"detail": "ابتدا Batch را پردازش کنید."})

        # 1) Incomplete rows block approval outright.
        blocking = batch.staged_students.filter(status=RowStatus.INCOMPLETE).count()
        if blocking > 0:
            raise ValidationError({
                "detail": (
                    f"{blocking} پرونده‌ی ناقص وجود دارد؛ تا رفع آن‌ها تأیید "
                    "نهایی ممکن نیست."
                )
            })

        # 2) Identity-level warnings (duplicates, invalid NID, ...) must have
        #    a human review resolution before approval.
        unresolved: list[dict] = []
        for s in batch.staged_students.prefetch_related("duplicate_resolutions").all():
            resolved_codes = {r.issue_code for r in s.duplicate_resolutions.all()}
            for issue in (s.validation_issues or []):
                code = issue.get("code")
                if code in IDENTITY_ISSUE_CODES and code not in resolved_codes:
                    unresolved.append({
                        "student_id": s.id,
                        "name": s.full_name,
                        "code": code,
                        "message": issue.get("message", ""),
                    })
        if unresolved:
            raise ValidationError({
                "detail": (
                    f"{len(unresolved)} هشدار هویتی حل‌نشده وجود دارد؛ پیش از "
                    "تأیید نهایی باید در صفحه‌ی «موارد نیازمند بررسی» تصمیم‌گیری شود."
                ),
                "unresolved": unresolved,
            })

        before = batch.status
        batch.status = BatchStatus.APPROVED
        batch.approved_at = timezone.now()
        batch.save(update_fields=["status", "approved_at", "updated_at"])
        record_audit(
            actor=request.user, action=AuditAction.BATCH_APPROVE,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            before_state={"status": before},
            after_state={"status": batch.status},
            request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    @action(detail=True, methods=["get"], url_path="students")
    def students(self, request, pk=None):
        from .serializers_rows import StagedStudentListSerializer

        batch = self.get_object()
        qs = batch.staged_students.all().prefetch_related("guardians")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        page = self.paginate_queryset(qs)
        ser = StagedStudentListSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(detail=True, methods=["get"], url_path="rows")
    def rows(self, request, pk=None):
        from .serializers_rows import ImportRowSerializer

        batch = self.get_object()
        qs = batch.rows.all()
        page = self.paginate_queryset(qs)
        ser = ImportRowSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        batch = self.get_object()
        before = batch.status
        batch.status = BatchStatus.ARCHIVED
        batch.archived_at = timezone.now()
        batch.save(update_fields=["status", "archived_at", "updated_at"])

        record_audit(
            actor=request.user, action=AuditAction.BATCH_ARCHIVE,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            before_state={"status": before}, after_state={"status": batch.status},
            request=request,
        )
        return Response(BatchDetailSerializer(batch).data)

    # ------------------------------------------------------------------
    # Exports (phase 6)
    # ------------------------------------------------------------------
    def _require_processed(self, batch):
        if not batch.staged_students.exists():
            raise ValidationError({"detail": "ابتدا Batch را پردازش کنید."})

    @action(detail=True, methods=["get"], url_path="export/errors")
    def export_errors(self, request, pk=None):
        batch = self.get_object()
        self._require_processed(batch)
        content = exports.build_error_report_xlsx(batch)
        record_audit(
            actor=request.user, action=AuditAction.EXPORT_ERRORS,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            request=request,
        )
        return exports.xlsx_response(content, f"batch-{batch.id}-errors.xlsx")

    @action(detail=True, methods=["get"], url_path="export/canonical/xlsx")
    def export_canonical_xlsx(self, request, pk=None):
        batch = self.get_object()
        self._require_processed(batch)
        content = exports.build_canonical_xlsx(batch)
        record_audit(
            actor=request.user, action=AuditAction.EXPORT_CANONICAL,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            request=request,
        )
        return exports.xlsx_response(content, f"batch-{batch.id}-canonical.xlsx")

    @action(detail=True, methods=["get"], url_path="export/canonical/json")
    def export_canonical_json(self, request, pk=None):
        batch = self.get_object()
        self._require_processed(batch)
        payload = exports.build_canonical_json(batch)
        record_audit(
            actor=request.user, action=AuditAction.EXPORT_CANONICAL,
            entity_type="ImportBatch", entity_id=batch.id, school=batch.school,
            request=request,
        )
        return exports.json_response(payload, f"batch-{batch.id}-canonical.json")


class MappingProfileViewSet(SchoolScopedQuerySetMixin, viewsets.ModelViewSet):
    """Reusable column-mapping profiles for the operator's school."""

    permission_classes = [IsSchoolOperator]
    serializer_class = MappingProfileSerializer
    queryset = MappingProfile.objects.all()

    def get_queryset(self):
        # SchoolScopedQuerySetMixin enforces tenant isolation.
        qs = super().get_queryset()
        return qs.filter(is_active=True).select_related("school")

    def perform_create(self, serializer):
        school = _resolve_school(self.request)
        profile = serializer.save(school=school, created_by=self.request.user)
        record_audit(
            actor=self.request.user,
            action=AuditAction.MAPPING_PROFILE_CREATE,
            entity_type="MappingProfile", entity_id=profile.id,
            school=school, after_state={"name": profile.name},
            request=self.request,
        )

    def perform_update(self, serializer):
        profile = serializer.save()
        record_audit(
            actor=self.request.user,
            action=AuditAction.MAPPING_PROFILE_UPDATE,
            entity_type="MappingProfile", entity_id=profile.id,
            school=profile.school, request=self.request,
        )


class StagedStudentViewSet(SchoolScopedQuerySetMixin, viewsets.GenericViewSet):
    """
    Read + manual-edit access to staged students for the operator's school.

    School isolation is enforced through the ``batch`` relation.
    """

    permission_classes = [IsSchoolOperator]
    serializer_class = StagedStudentDetailSerializer
    queryset = StagedStudent.objects.all()
    school_field = "batch__school"
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("batch", "source_row").prefetch_related("guardians")

    def get_serializer_class(self):
        if self.action == "list":
            from .serializers_rows import StagedStudentListSerializer
            return StagedStudentListSerializer
        return StagedStudentDetailSerializer

    def list(self, request):
        qs = self.get_queryset()
        batch_id = request.query_params.get("batch")
        status_filter = request.query_params.get("status")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        from .serializers_rows import StagedStudentListSerializer
        ser = StagedStudentListSerializer(qs, many=True)
        return Response(ser.data)

    def retrieve(self, request, pk=None):
        student = self.get_object()
        return Response(StagedStudentDetailSerializer(student).data)

    def partial_update(self, request, pk=None):
        from .serializers_editing import StudentPatchSerializer, apply_student_edit

        student = self.get_object()
        if student.batch.status not in {
            BatchStatus.UPLOADED,
            BatchStatus.MAPPING_REQUIRED,
            BatchStatus.REVIEW_REQUIRED,
            BatchStatus.VALIDATED,
            BatchStatus.FAILED,
        }:
            raise ValidationError({"detail": "این پرونده در وضعیت فعلی قابل ویرایش نیست."})

        ser = StudentPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data

        # Snapshot previous field values for the audit log. Audit records
        # which fields changed, old value, new value, reason, and reviewer.
        changed_fields = [
            f for f in payload.keys()
            if f != "edit_reason"
        ]
        before_fields = {}
        after_fields = {}
        for f in changed_fields:
            if f == "emergency_mobile":
                before_fields[f] = (student.contacts or {}).get("emergency_mobile")
            else:
                before_fields[f] = getattr(student, f, None)

        edited = apply_student_edit(student, payload, request.user)

        for f in changed_fields:
            if f == "emergency_mobile":
                after_fields[f] = (edited.contacts or {}).get("emergency_mobile")
            else:
                after_fields[f] = getattr(edited, f, None)

        record_audit(
            actor=request.user,
            action=AuditAction.STUDENT_UPDATE,
            entity_type="StagedStudent",
            entity_id=edited.id,
            school=student.batch.school,
            before_state={
                "batch_id": student.batch_id,
                "changed_fields": changed_fields,
                "fields": before_fields,
            },
            after_state={
                "batch_id": student.batch_id,
                "changed_fields": changed_fields,
                "fields": after_fields,
                "edit_reason": payload.get("edit_reason"),
            },
            request=request,
        )
        return Response(StagedStudentDetailSerializer(edited).data)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        """
        Record a manual decision about an identity-level warning.

        Resolution does NOT merge or delete anything: it just stores a
        reviewer's decision so a Batch with identity warnings can proceed
        to approval once every warning is resolved.
        """
        from .serializers_review import DuplicateResolutionSerializer

        student = self.get_object()
        ser = DuplicateResolutionSerializer(data=request.data, context={"student": student})
        ser.is_valid(raise_exception=True)

        # Pull the other student ids referenced by the issue so the
        # resolution record is self-contained.
        issue = next(
            (
                i for i in (student.validation_issues or [])
                if i.get("code") == ser.validated_data["issue_code"]
            ),
            {},
        )
        other_ids = issue.get("other_student_ids") or []

        resolution = student.duplicate_resolutions.create(
            issue_code=ser.validated_data["issue_code"],
            decision=ser.validated_data["decision"],
            review_note=ser.validated_data["review_note"],
            reviewer=request.user,
            reviewer_username=request.user.username,
            other_student_ids=other_ids,
        )

        # If the decision is CORRECTED_SOURCE, the operator has already
        # edited the row via PATCH; re-run cross-row validation so the
        # warning disappears if truly fixed. Otherwise leave the issue in
        # place but mark it resolved via the related record.
        if ser.validated_data["decision"] == "corrected_source":
            validate_batch(student.batch)

        record_audit(
            actor=request.user,
            action=AuditAction.STUDENT_STATUS_CHANGE,
            entity_type="StagedStudent",
            entity_id=student.id,
            school=student.batch.school,
            after_state={
                "resolution": resolution.decision,
                "issue_code": resolution.issue_code,
                "review_note": resolution.review_note,
            },
            request=request,
        )
        from .serializers_review import DuplicateResolutionSerializer as Out
        return Response(Out(resolution).data, status=201)


class CanonicalFieldsView(APIView):
    """Return the canonical field vocabulary (for the mapping UI)."""

    permission_classes = [IsSchoolOperator]

    def get(self, request):
        from .constants import CANONICAL_FIELD_GROUPS

        fields = [
            {"path": path, "label": label} for path, label in CANONICAL_FIELDS.items()
        ]
        groups = [
            {"id": gid, "label": glabel, "fields": gfields}
            for gid, glabel, gfields in CANONICAL_FIELD_GROUPS
        ]
        return Response({"fields": fields, "groups": groups})
