import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PortalUser
from apps.schools.models import SchoolTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def schools(db):
    s1 = SchoolTenant.objects.create(name="مدرسه الف", external_code="A-01")
    s2 = SchoolTenant.objects.create(name="مدرسه ب", external_code="B-02")
    return s1, s2


@pytest.fixture
def operator_a(db, schools):
    s1, _ = schools
    user = PortalUser.objects.create_user(
        username="op_a",
        password="StrongPass@123",
        role=PortalUser.Role.OPERATOR,
        school_tenant=s1,
    )
    return user


@pytest.fixture
def operator_b(db, schools):
    _, s2 = schools
    user = PortalUser.objects.create_user(
        username="op_b",
        password="StrongPass@123",
        role=PortalUser.Role.OPERATOR,
        school_tenant=s2,
    )
    return user


@pytest.fixture
def admin_user(db):
    return PortalUser.objects.create_superuser(
        username="root",
        password="StrongRoot@123",
        role=PortalUser.Role.ADMIN,
    )


@pytest.fixture
def auth_client(api_client):
    def _login(user, password="StrongPass@123"):
        # Bypass throttle for tests.
        from rest_framework.test import force_authenticate

        api_client.force_authenticate(user=user)
        return api_client

    return _login
