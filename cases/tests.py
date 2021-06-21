import pytest
from pytest_django.asserts import assertContains
from .models import Case

pytestmark = pytest.mark.django_db


@pytest.fixture
def case_1(db):
    return Case.objects.create(kind="diy")


@pytest.fixture
def case_other_uprn(db):
    return Case.objects.create(uprn=10001, kind="other", kind_other="Wombat")


def test_list(admin_client, case_1):
    response = admin_client.get("/cases")
    assertContains(response, "Cases")


def test_case_not_found(admin_client):
    response = admin_client.get("/cases/1")
    assertContains(response, "Not Found", status_code=404)


def test_case(admin_client, case_1):
    response = admin_client.get(f"/cases/{case_1.id}")
    assertContains(response, "DIY")


def test_case_uprn(admin_client, case_other_uprn):
    response = admin_client.get(f"/cases/{case_other_uprn.id}")
    assertContains(response, "Wombat")
    assertContains(response, "10001")
