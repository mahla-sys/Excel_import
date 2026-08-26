"""
Tests for smart column suggestions and mapping persistence.

Covers the most important UX requirement: duplicate headers (e.g. three
columns all labeled "کدملی") must be disambiguated by their positional
context so the student/father/mother variants map correctly.
"""
import pytest

from apps.intake.constants import CANONICAL_FIELDS
from apps.intake.mapping import ensure_no_duplicate_targets, suggest_mappings
from apps.intake.models import ImportBatch
from apps.intake.tests.factories import sample_enrollment_xlsx

from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def test_suggestions_disambiguate_duplicate_national_ids():
    columns = [
        {"index": 0, "label": "نام"},
        {"index": 1, "label": "نام خانوادگی"},
        {"index": 2, "label": "کدملی"},
        {"index": 3, "label": "پایه"},
        {"index": 4, "label": "موبایل پدر"},
        {"index": 5, "label": "نام پدر"},
        {"index": 6, "label": "کدملی"},
        {"index": 7, "label": "نام مادر"},
        {"index": 8, "label": "کدملی"},
    ]
    suggestions = suggest_mappings(columns)
    by_index = {s.column_index: s for s in suggestions}

    assert by_index[2].target == "student.national_id"
    assert by_index[6].target == "guardian.father.national_id"
    assert by_index[8].target == "guardian.mother.national_id"

    # First column gets high confidence; duplicates are medium/low with reason.
    assert by_index[2].confidence == "high"
    assert by_index[6].confidence in {"medium", "low"}
    assert by_index[6].reason


def test_suggestions_ignore_empty_label():
    columns = [{"index": 0, "label": ""}, {"index": 1, "label": "نام"}]
    suggestions = suggest_mappings(columns)
    assert suggestions[0].target is None
    assert suggestions[1].target == "student.first_name"


def test_suggestions_normalize_arabic_ye_and_kaf():
    columns = [
        {"index": 0, "label": "نام خانوادگي"},  # Arabic yeh
        {"index": 1, "label": "كدملي"},  # Arabic kaf + yeh
    ]
    suggestions = suggest_mappings(columns)
    assert suggestions[0].target == "student.last_name"
    assert suggestions[1].target == "student.national_id"


def test_duplicate_target_warning():
    mapping = {
        "student.first_name": {"source_column_index": 0},
        "student.last_name": {"source_column_index": 0},
    }
    warnings = ensure_no_duplicate_targets(mapping)
    assert len(warnings) == 1


def _upload_batch(api_client, operator_a):
    f = SimpleUploadedFile(
        "sample.xlsx",
        sample_enrollment_xlsx(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    api_client.force_authenticate(operator_a)
    resp = api_client.post(
        "/api/v1/intake/batches/upload/",
        data={"file": f, "academic_year_label": "1405-1406"},
        format="multipart",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 201, resp.data
    return resp.data["id"]


def test_suggestions_endpoint(api_client, operator_a):
    batch_id = _upload_batch(api_client, operator_a)
    api_client.post(
        f"/api/v1/intake/batches/{batch_id}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    resp = api_client.get(
        f"/api/v1/intake/batches/{batch_id}/mapping/suggestions/",
        SERVER_NAME="localhost",
    )
    assert resp.status_code == 200
    suggestions = {s["column_index"]: s for s in resp.data["suggestions"]}
    assert suggestions[2]["target"] == "student.national_id"
    assert suggestions[6]["target"] == "guardian.father.national_id"
    assert suggestions[8]["target"] == "guardian.mother.national_id"


def test_save_mapping_persists_snapshot(api_client, operator_a):
    batch_id = _upload_batch(api_client, operator_a)
    api_client.post(
        f"/api/v1/intake/batches/{batch_id}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    payload = {
        "mappings": {
            "student.first_name": {"source_column_index": 0, "source_column_label": "نام"},
            "student.last_name": {"source_column_index": 1, "source_column_label": "نام خانوادگی"},
            "student.national_id": {"source_column_index": 2, "source_column_label": "کدملی"},
            "enrollment.grade": {"source_column_index": 3, "source_column_label": "پایه"},
        },
        "unknown_columns": [
            {"index": 4, "label": "موبایل پدر", "action": "extra_attribute"},
        ],
        "save_as_profile": "قالب پایه هفتم",
    }
    resp = api_client.post(
        f"/api/v1/intake/batches/{batch_id}/mapping/",
        data=payload, format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    batch = ImportBatch.objects.get(pk=batch_id)
    assert batch.mapping_snapshot is not None
    assert batch.mapping_profile is not None
    assert batch.mapping_profile.version == 1
    assert batch.mapping_profile.mappings["student.national_id"]["source_column_index"] == 2


def test_accept_suggestions_seeds_mapping(api_client, operator_a):
    batch_id = _upload_batch(api_client, operator_a)
    api_client.post(
        f"/api/v1/intake/batches/{batch_id}/select-header/",
        data={"header_row": 1}, format="json", SERVER_NAME="localhost",
    )
    resp = api_client.post(
        f"/api/v1/intake/batches/{batch_id}/mapping/",
        data={"accept_suggestions": True, "mappings": {}},
        format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 200, resp.data
    batch = ImportBatch.objects.get(pk=batch_id)
    targets = set(batch.mapping_snapshot["mappings"].keys())
    assert "student.national_id" in targets
    assert "guardian.father.national_id" in targets
    assert "guardian.mother.national_id" in targets


def test_operator_b_cannot_save_mapping_on_a_batch(api_client, operator_a, operator_b):
    batch_id = _upload_batch(api_client, operator_a)
    api_client.force_authenticate(operator_b)
    resp = api_client.post(
        f"/api/v1/intake/batches/{batch_id}/mapping/",
        data={"mappings": {}}, format="json", SERVER_NAME="localhost",
    )
    assert resp.status_code == 404
