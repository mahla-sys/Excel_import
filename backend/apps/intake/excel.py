"""
Workbook inspection helpers built strictly on openpyxl in read-only mode.

pandas is intentionally not used: it can convert national IDs / phone
numbers with leading zeros into numeric types and silently corrupt data.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from openpyxl import load_workbook

from .constants import IssueCode


class WorkbookInspectionError(Exception):
    """Raised when an uploaded file cannot be parsed as a valid .xlsx."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class ColumnInfo:
    index: int  # 0-based
    letter: str
    label: str
    samples: list[str] = field(default_factory=list)


@dataclass
class SheetInfo:
    name: str
    max_row: int
    max_column: int


# XLSX files are ZIP archives that start with the PK signature. We use this
# as a cheap pre-check before handing the file to openpyxl.
_XLSX_MAGIC = b"PK\x03\x04"


def validate_uploaded_file(file_obj) -> int:
    """
    Validate size/extension/signature of an uploaded file.

    Returns its size in bytes. Raises ``WorkbookInspectionError`` with a
    structured ``code`` on failure.
    """
    size = getattr(file_obj, "size", 0) or 0
    max_bytes = int(getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024))
    if size > max_bytes:
        raise WorkbookInspectionError(
            IssueCode.FILE_TOO_LARGE,
            f"حجم فایل بیش از حد مجاز است ({max_bytes // (1024*1024)} مگابایت).",
        )
    if size == 0:
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE, "فایل خالی است."
        )

    name = (getattr(file_obj, "name", "") or "").lower()
    if not name.endswith(".xlsx"):
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE,
            "فقط فایل‌های .xlsx پشتیبانی می‌شوند.",
        )

    # Read a small header to confirm the ZIP signature.
    file_obj.seek(0)
    header = file_obj.read(4)
    file_obj.seek(0)
    if header[:4] != _XLSX_MAGIC:
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE,
            "محتوای فایل معتبر نیست؛ یک فایل .xlsx واقعی انتخاب کنید.",
        )
    return size


def list_sheets(file_obj) -> list[SheetInfo]:
    """
    Return the list of sheets with their dimensions.

    The caller is responsible for resetting the file pointer if needed;
    this function seeks to 0 on entry and on exit.
    """
    file_obj.seek(0)
    try:
        wb = load_workbook(
            file_obj, read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:  # openpyxl raises many things on bad files
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE, f"خواندن فایل Excel ممکن نیست: {exc}"
        ) from exc

    sheets: list[SheetInfo] = []
    try:
        for ws in wb.worksheets:
            # openpyxl's max_row/max_column can be over-reported for sparse
            # sheets, but they are cheap and good enough for a preview.
            sheets.append(
                SheetInfo(
                    name=ws.title,
                    max_row=ws.max_row or 0,
                    max_column=ws.max_column or 0,
                )
            )
    finally:
        wb.close()
    file_obj.seek(0)
    return sheets


def inspect_columns(
    file_obj, sheet_name: str, header_row: int, sample_rows: int = 5
) -> list[ColumnInfo]:
    """
    Read the header row of ``sheet_name`` at ``header_row`` (1-indexed) and
    return one ``ColumnInfo`` per non-empty column, with up to
    ``sample_rows`` sample values drawn from rows immediately below.

    Empty cells in the header row terminate the column scan (the first
    run of non-empty labels is used); this matches how school spreadsheets
    are structured in practice.
    """
    if header_row < 1:
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE, "شماره ردیف هدر باید حداقل ۱ باشد."
        )

    file_obj.seek(0)
    try:
        wb = load_workbook(
            file_obj, read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE, f"خواندن فایل ممکن نیست: {exc}"
        ) from exc

    if sheet_name not in wb.sheetnames:
        wb.close()
        raise WorkbookInspectionError(
            IssueCode.FILE_TYPE, f"برگه‌ای با نام «{sheet_name}» پیدا نشد."
        )

    ws = wb[sheet_name]
    columns: list[ColumnInfo] = []

    try:
        row_iter = ws.iter_rows(min_row=header_row, values_only=True)
        try:
            header_values = next(row_iter)
        except StopIteration:
            raise WorkbookInspectionError(
                IssueCode.FILE_TYPE, "ردیف هدر در فایل خالی است."
            )

        # Build columns from the header.
        for idx, raw in enumerate(header_values):
            label = _to_clean_str(raw)
            if not label:
                continue
            columns.append(
                ColumnInfo(
                    index=idx,
                    letter=_column_letter(idx),
                    label=label,
                    samples=[],
                )
            )

        if not columns:
            raise WorkbookInspectionError(
                IssueCode.FILE_TYPE,
                "هیچ عنوان ستونی در ردیف هدر انتخاب‌شده پیدا نشد.",
            )

        # Collect samples from the next N rows. We deliberately do not
        # normalize here; this is a raw preview for the operator.
        for sample_offset, row in enumerate(row_iter):
            if sample_offset >= sample_rows:
                break
            for col in columns:
                if col.index < len(row):
                    val = _to_clean_str(row[col.index])
                    if val:
                        col.samples.append(val)
    finally:
        wb.close()
        file_obj.seek(0)

    return columns


def count_data_rows(file_obj, sheet_name: str, header_row: int) -> int:
    """
    Count rows below the header that contain at least one non-empty cell.

    This is used to enforce the MAX_UPLOAD_ROWS limit before processing.
    """
    file_obj.seek(0)
    wb = load_workbook(file_obj, read_only=True, data_only=True, keep_links=False)
    try:
        ws = wb[sheet_name]
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if any(cell is not None and str(cell).strip() != "" for cell in row):
                count += 1
        return count
    finally:
        wb.close()
        file_obj.seek(0)


def _to_clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        # Preserve leading-zero concerns for national IDs/phones by using
        # the string form; normalization happens later in phase 3.
        return str(int(value))
    return str(value).strip()


def _column_letter(zero_based_index: int) -> str:
    """Convert 0-based column index to spreadsheet letters (0 -> A, 25 -> Z, 26 -> AA)."""
    n = zero_based_index + 1
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
