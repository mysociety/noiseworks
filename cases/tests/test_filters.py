import re
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.contrib.gis.geos import Point
from accounts.models import User
from ..models import Case, Complaint

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
        phone="+447900000000",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def case_1(db, staff_user, normal_user):
    return Case.objects.create(
        kind="other",
        kind_other="Fireworks",
        location_cache="123 High Street, Hackney",
        assigned=staff_user,
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def case_location(db):
    return Case.objects.create(kind="diy", point=Point(470267, 122766), radius=100)


def test_list(admin_client, case_1):
    response = admin_client.get("/cases")
    assertContains(response, "Cases")


def test_assigned_filter(admin_client, admin_user, case_1, case_location):
    response = admin_client.get("/cases?assigned=others")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = admin_user
    case_1.save()
    response = admin_client.get("/cases?assigned=me")
    assertContains(response, f"/cases/{case_1.id}")
    response = admin_client.get(f"/cases?assigned={admin_user.id}")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = None
    case_1.save()
    response = admin_client.get("/cases?assigned=none")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.followers.add(admin_user)
    response = admin_client.get("/cases?assigned=following")
    assertContains(response, f"/cases/{case_1.id}")


def test_ward_filter(admin_client, admin_user, case_1):
    admin_user.wards = ["E05009374"]
    admin_user.save()
    response = admin_client.get(
        "/cases?" + "&".join(f"ward={ward}" for ward in admin_user.wards)
    )
    assertNotContains(response, f"/cases/{case_1.id}")
    admin_user.wards = ["E05009372", case_1.ward]
    admin_user.save()
    response = admin_client.get(
        "/cases?" + "&".join(f"ward={ward}" for ward in admin_user.wards)
    )
    assertContains(response, f"/cases/{case_1.id}")


def test_ward_group_filter(admin_client, admin_user, case_1):
    response = admin_client.get("/cases?ward=south")
    assertNotContains(response, f"/cases/{case_1.id}")
    response = admin_client.get("/cases?ward=north")
    assertContains(response, f"/cases/{case_1.id}")


def test_search(admin_client, case_1):
    resp = admin_client.get("/cases?search=fireworks&ajax=1")
    assertContains(resp, "Fireworks")
    resp = admin_client.get(f"/cases?search={case_1.id}")
    assertContains(resp, "Fireworks")


def test_search_multiple_spaces(admin_client, case_1):
    resp = admin_client.get("/cases?search=123+high+street")
    assertContains(resp, "Fireworks")


def test_search_phone(admin_client, case_1):
    Complaint.objects.create(
        case=case_1, complainant=case_1.created_by, happening_now=True
    )
    resp = admin_client.get(f"/cases?search=07900000000")
    assertContains(resp, "Fireworks")


def test_search_name(admin_client, case_1):
    Complaint.objects.create(
        case=case_1, complainant=case_1.created_by, happening_now=True
    )
    resp = admin_client.get(f"/cases?search=Normal+User")
    assertContains(resp, "Fireworks")


def test_search_merged_case(admin_client):
    c1 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Combined case",
        point=Point(470267, 122766),
    )
    c2 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Merged case",
        point=Point(470267, 122766),
    )
    c1.actions.create(case_old=c2)
    resp = admin_client.get(f"/cases?search={c2.id}")
    assertContains(resp, "Merged case")


def test_user_ward_js_array(admin_client):
    resp = admin_client.get(f"/cases")
    assertContains(resp, "nw.user_wards = []")
