"""Helpers for building in-memory .xlsx files in tests."""
from __future__ import annotations

import io

from openpyxl import Workbook


def build_xlsx_bytes(sheets: dict[str, list[list]]) -> bytes:
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def sample_enrollment_xlsx() -> bytes:
    """
    A small sample with a duplicate 'کدملی' header (student/father/mother).
    National IDs below are structurally valid (correct checksum).
    """
    return build_xlsx_bytes({
        "ثبت‌نام": [
            ["نام", "نام خانوادگی", "کدملی", "پایه",
             "موبایل پدر", "نام پدر", "کدملی",
             "نام مادر", "کدملی"],
            ["علی", "رضایی", "0012345679", "هفتم",
             "09120000000", "حسین", "1111111111",
             "مریم", "1111111111"],
            ["زهرا", "احمدی", "0123456789", "هشتم",
             "09120000001", "رضا", "1111111111",
             "فاطمه", "1111111111"],
        ],
    })
