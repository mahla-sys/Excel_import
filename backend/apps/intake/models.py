from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

from .constants import (
    AdmissionStatus,
    BatchStatus,
    IssueSeverity,
    PlacementStatus,
    RowStatus,
)
from .storage import build_private_path, private_storage


# Identity-level issue codes that block Batch approval until the operator
# resolves them manually (or confirms the students are distinct).
IDENTITY_ISSUE_CODES = (
    "W-DUPLICATE-EXACT",
    "W-DUPLICATE-SUSPECTED",
    "E-NID-CHECKSUM",
    "E-NID-LENGTH",
    "E-NID-DIGITS",
)


class ImportBatch(TimeStampedModel):
    """
    One uploaded registration file for one school.

    A Batch holds the original (private) file plus all metadata about how
    it should be interpreted (sheet, header, mapping snapshot) and where
    it is in the pipeline. Rows/students are attached in later phases.

    ``academic_year_label`` is entered MANUALLY by the school operator at
    upload time; the server never infers it from the clock because the file
    may belong to a past or upcoming registration cycle.
    """

    school = models.ForeignKey(
        "schools.SchoolTenant",
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_batches",
    )

    # --- File metadata ---
    original_filename = models.CharField(max_length=300)
    private_storage_path = models.CharField(max_length=500, unique=True)
    file_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hex digest of the uploaded file.",
        db_index=True,
    )
    file_size = models.PositiveBigIntegerField()

    # --- Academic context (manual, never auto-derived from server clock) ---
    academic_year_label = models.CharField(
        max_length=20,
        help_text="مثلاً 1405-1406؛ توسط مسئول مدرسه وارد می‌شود.",
    )
    notes = models.TextField(blank=True)

    # --- Pipeline metadata ---
    status = models.CharField(
        max_length=40,
        choices=BatchStatus.choices,
        default=BatchStatus.UPLOADED,
        db_index=True,
    )

    # Workbook discovery (filled by inspect_workbook after upload)
    workbook_sheets = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {name, max_row, max_column} discovered in the file.",
    )
    selected_sheet = models.CharField(max_length=200, blank=True)

    # Header row (1-indexed as openpyxl uses).
    header_row_number = models.PositiveIntegerField(null=True, blank=True)

    # Columns discovered for the selected sheet/header:
    # [{"index": 0, "letter": "A", "label": "نام", "samples": ["علی", ...]}]
    detected_columns = models.JSONField(default=list, blank=True)

    # The mapping chosen for this batch (a snapshot; mapping_profile is the
    # reusable source). It is {canonical_field: {source_column_index, source_column_label}}.
    mapping_profile = models.ForeignKey(
        "intake.MappingProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    mapping_snapshot = models.JSONField(null=True, blank=True)

    # Processing stats / counters. Populated after processing (phase 4).
    stats = models.JSONField(default=dict, blank=True)

    # Timestamps for the pipeline.
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    # When status=FAILED, the technical error is stored here (never shown
    # to operators verbatim; used by system admins).
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["school", "-uploaded_at"]),
        ]
        verbose_name_plural = "Import batches"

    def __str__(self) -> str:
        return f"Batch #{self.pk} ({self.school.name} — {self.academic_year_label})"

    # --- Convenience helpers used by views / services ---
    @property
    def is_editable(self) -> bool:
        return self.status in {
            BatchStatus.UPLOADED,
            BatchStatus.MAPPING_REQUIRED,
            BatchStatus.REVIEW_REQUIRED,
            BatchStatus.VALIDATED,
        }

    def save_private_file(self, uploaded_file, school_id: int) -> None:
        """Save ``uploaded_file`` to private storage with a UUID name."""
        path = build_private_path(school_id, uploaded_file.name)
        name = private_storage.save(path, uploaded_file)
        self.private_storage_path = name

    def open_private_file(self):
        return private_storage.open(self.private_storage_path, "rb")


class MappingProfile(TimeStampedModel):
    """
    A reusable column-mapping configuration scoped to a school.

    ``mappings`` structure::

        {
          "student.first_name": {"source_column_index": 2, "source_column_label": "نام"},
          ...
        }

    ``unknown_columns`` records columns that the operator explicitly chose
    to ignore or store as extra attributes, so no column is ever silently
    dropped.

    Versioning: every time a profile is edited its ``version`` is bumped
    and the prior snapshot is appended to ``history`` (list of
    {version, mappings, unknown_columns, edited_by, edited_at}).
    """

    school = models.ForeignKey(
        "schools.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="mapping_profiles",
    )
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    source_file_hint = models.CharField(max_length=300, blank=True)
    sheet_name_hint = models.CharField(max_length=200, blank=True)
    header_row_hint = models.PositiveIntegerField(null=True, blank=True)

    mappings = models.JSONField(default=dict, blank=True)
    unknown_columns = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of {index, label, action} where action is one of "
            "'extra_attribute' | 'ignored' | 'requires_decision'."
        ),
    )
    history = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_mapping_profiles",
    )

    class Meta:
        ordering = ["school", "-is_active", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                condition=models.Q(is_active=True),
                name="unique_active_mapping_name_per_school",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} (v{self.version})"


class ImportRow(models.Model):
    """
    A single raw row extracted from an uploaded workbook.

    ``raw_data`` is the verbatim cell values as openpyxl returned them
    (list of values), and is NEVER replaced by normalization. ``normalized_data``
    is the canonical/cleaned version produced by the normalize engine.

    Rows where no student could be constructed (e.g. completely blank or
    missing a name) are still kept here with their issues — no row is
    silently dropped.
    """

    batch = models.ForeignKey(
        "ImportBatch",
        on_delete=models.CASCADE,
        related_name="rows",
    )
    row_number = models.PositiveIntegerField(
        help_text="1-based row number in the original sheet (including header).",
    )
    raw_data = models.JSONField(default=list)
    normalized_data = models.JSONField(null=True, blank=True)
    validation_issues = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=RowStatus.choices, default=RowStatus.DRAFT)
    source_hash = models.CharField(max_length=64, blank=True)
    staged_student = models.ForeignKey(
        "StagedStudent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_rows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number"],
                name="uniq_row_per_batch",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "status"]),
        ]

    def __str__(self) -> str:
        return f"Batch#{self.batch_id} row {self.row_number} [{self.status}]"


class StagedStudent(TimeStampedModel):
    """
    A student record in the intake portal's staging area.

    This is NOT a Person in the main system; it is a cleaned, validated
    projection of one or more raw rows, ready for a future connector to
    read. Identity resolution (merging two StagedStudents) is NEVER
    automatic — duplicates are flagged for human review.
    """

    batch = models.ForeignKey(
        "ImportBatch",
        on_delete=models.CASCADE,
        related_name="staged_students",
    )
    source_row = models.OneToOneField(
        "ImportRow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student",
    )

    # Identity (canonical)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=200, blank=True)
    full_name = models.CharField(max_length=350, blank=True)
    national_id = models.CharField(max_length=20, blank=True, db_index=True)
    national_id_valid = models.BooleanField(null=True, blank=True)
    source_student_code = models.CharField(max_length=64, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    birth_date_raw = models.CharField(max_length=60, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    birth_place = models.CharField(max_length=200, blank=True)

    # Enrollment
    academic_year = models.CharField(max_length=20)
    grade = models.CharField(max_length=50, blank=True)
    classroom_title = models.CharField(max_length=100, blank=True)
    placement_status = models.CharField(
        max_length=20,
        choices=PlacementStatus.choices,
        default=PlacementStatus.PENDING,
    )
    admission_status = models.CharField(
        max_length=20,
        choices=AdmissionStatus.choices,
        default=AdmissionStatus.CONFIRMED,
    )

    # Structured JSON bags (contain raw + normalized + provenance per field)
    contacts = models.JSONField(default=dict, blank=True)
    admission_data = models.JSONField(default=dict, blank=True)
    extra_attributes = models.JSONField(default=dict, blank=True)

    # Per-field provenance: {field_path: {batch_id, row_number, column_index,
    # column_label, raw_value, normalized_value, last_edited_by?, edited_at?, edit_reason?}}
    field_provenance = models.JSONField(default=dict, blank=True)

    # Validation and review
    validation_issues = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=32,
        choices=RowStatus.choices,
        default=RowStatus.DRAFT,
        db_index=True,
    )
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["batch", "id"]
        indexes = [
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["national_id", "batch"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name or 'بدون نام'} ({self.national_id or '—'})"


class StagedGuardian(TimeStampedModel):
    """
    Guardian/father/mother tied to one StagedStudent in this intake portal.

    Guardians are NOT merged across students in v1; the future connector
    makes that decision based on the main system's identity model.
    """

    class RelationType(models.TextChoices):
        FATHER = "father", "پدر"
        MOTHER = "mother", "مادر"
        GUARDIAN = "guardian", "قیم"
        OTHER = "other", "سایر"
        UNKNOWN = "unknown", "نامشخص"

    student = models.ForeignKey(
        StagedStudent,
        on_delete=models.CASCADE,
        related_name="guardians",
    )
    relation_type = models.CharField(max_length=16, choices=RelationType.choices)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=200, blank=True)
    full_name = models.CharField(max_length=350, blank=True)
    national_id = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    birth_date_raw = models.CharField(max_length=60, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    education_level = models.CharField(max_length=100, blank=True)
    field_of_study = models.CharField(max_length=150, blank=True)
    employment_status = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    workplace_address = models.TextField(blank=True)
    extra_attributes = models.JSONField(default=dict, blank=True)
    field_provenance = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.full_name or '—'} ({self.get_relation_type_display()})"


class DuplicateResolution(TimeStampedModel):
    """
    A human decision about an identity-level warning on a StagedStudent.

    Resolution NEVER merges or deletes records — it merely records that a
    human has looked at the warning and decided how to treat it. A Batch
    cannot be approved while any of its students has an unresolved identity
    warning (i.e. has such a code in ``validation_issues`` without a
    corresponding ``DuplicateResolution``).
    """

    class Resolution(models.TextChoices):
        CONFIRMED_DUPLICATE = "confirmed_duplicate", "تکراری تأیید شد"
        CONFIRMED_DISTINCT = "confirmed_distinct_people", "افراد متفاوت تأیید شد"
        CORRECTED_SOURCE = "corrected_source_data", "داده منبع اصلاح شد"
        NEEDS_FOLLOW_UP = "needs_follow_up", "نیازمند پیگیری"

    student = models.ForeignKey(
        StagedStudent,
        on_delete=models.CASCADE,
        related_name="duplicate_resolutions",
    )
    issue_code = models.CharField(max_length=40)
    decision = models.CharField(max_length=32, choices=Resolution.choices)
    review_note = models.TextField()
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicate_reviews",
    )
    reviewer_username = models.CharField(max_length=150, blank=True)
    # Snapshot of the other student(s) referenced by the warning at decision
    # time, so the record survives even if those rows change.
    other_student_ids = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "issue_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} / {self.issue_code} -> {self.decision}"
