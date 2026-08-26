"""
Private file storage for raw uploaded Excel files.

Files are stored under ``PRIVATE_STORAGE_ROOT`` (outside ``MEDIA_ROOT``),
with UUID-based names that contain no trace of the original filename. They
are NEVER served by Django's static/media system; access goes exclusively
through an authenticated, tenant-checked download view
(``OriginalFileDownloadView``).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateFileSystemStorage(FileSystemStorage):
    """
    FileSystemStorage rooted at ``PRIVATE_STORAGE_ROOT``.

    ``.url()`` raises because there is no public URL for raw files.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(settings.PRIVATE_STORAGE_ROOT))
        kwargs.setdefault("file_permissions_mode", 0o640)
        kwargs.setdefault("directory_permissions_mode", 0o750)
        super().__init__(*args, **kwargs)

    def url(self, name):  # pragma: no cover - defensive
        raise NotImplementedError(
            "Private raw files have no public URL; use the authenticated "
            "download endpoint instead."
        )


private_storage = PrivateFileSystemStorage()


def build_private_path(school_id: int, original_filename: str) -> str:
    """
    Return the relative storage path for a new upload.

    Layout: ``raw/<school_id>/<year>/<uuid>.xlsx``

    The original filename is intentionally NOT part of the path; it is
    stored only in the database as metadata.
    """
    from django.utils import timezone

    year = timezone.now().strftime("%Y")
    ext = Path(original_filename).suffix.lower() or ".xlsx"
    if ext != ".xlsx":  # Defensive; upload validation enforces .xlsx earlier.
        ext = ".xlsx"
    return f"raw/{school_id}/{year}/{uuid.uuid4().hex}{ext}"
