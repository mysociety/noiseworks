import re
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.contrib.gis.geos import Point
from accounts.models import User
from ..models import Case

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(db):
    return User.objects.create(is_staff=True, username="staffuser1")


@pytest.fixture
def normal_user(db):
    return User.objects.create(
        username="normal@example.org",
        email="normal@example.org",
        email_verified=True,
        phone="+447700900123",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def case_1(db, staff_user, normal_user):
    return Case.objects.create(
        kind="diy", assigned=staff_user, created_by=normal_user, ward="E05009373"
    )


@pytest.fixture
def case_location(db):
    return Case.objects.create(kind="diy", point=Point(470267, 122766), radius=100)


def test_list(admin_client, case_1):
    response = admin_client.get("/cases")
    assertContains(response, "Cases")


def test_assigned_filter(
    admin_client, admin_user, case_1, case_location, requests_mock
):
    requests_mock.get(re.compile("greenspaces/ows"), json={"features": []})
    requests_mock.get(re.compile("transport/ows"), json={"features": []})
    response = admin_client.get("/cases?assigned=others")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = admin_user
    case_1.save()
    response = admin_client.get("/cases")
    assertContains(response, f"/cases/{case_1.id}")
    response = admin_client.get(f"/cases?assigned={admin_user.id}")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = None
    case_1.save()
    response = admin_client.get("/cases?assigned=none")
    assertContains(response, f"/cases/{case_1.id}")


def test_ward_filter(admin_client, admin_user, case_1):
    admin_user.wards = ["E05009374"]
    admin_user.save()
    response = admin_client.get("/cases?assigned=")
    assertNotContains(response, f"/cases/{case_1.id}")
    admin_user.wards = ["E05009372", case_1.ward]
    admin_user.save()
    response = admin_client.get("/cases?assigned=")
    assertContains(response, f"/cases/{case_1.id}")
