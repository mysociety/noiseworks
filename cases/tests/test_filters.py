import pytest
from datetime import timedelta
from django.contrib.gis.geos import Point
from functools import partial
from pytest_django.asserts import assertContains, assertNotContains

from accounts.models import User

from ..models import Action, ActionType, Case, Complaint

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
        estate="?",
        assigned=staff_user,
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def case_2(db, staff_user, normal_user):
    return Case.objects.create(
        kind="other",
        kind_other="Fireworks",
        location_cache="123 High Street, Hackney",
        estate="?",
        assigned=staff_user,
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def case_location(db):
    return Case.objects.create(
        kind="diy",
        point=Point(470267, 122766),
        radius=100,
        location_cache="Location",
        estate="?",
    )


@pytest.fixture
def action_type(db):
    ActionType.objects.create(name="An action type", common=True),


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


def test_assigned_filter_not_assigned_anything(
    admin_client, admin_user, case_1, case_location
):
    response = admin_client.get(f"/cases?assigned={case_1.created_by.id}")
    assertNotContains(response, f"/cases/{case_1.id}")


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
    resp = admin_client.get("/cases?search=07900000000")
    assertContains(resp, "Fireworks")


def test_search_name(admin_client, case_1):
    Complaint.objects.create(
        case=case_1, complainant=case_1.created_by, happening_now=True
    )
    resp = admin_client.get("/cases?search=Normal+User")
    assertContains(resp, "Fireworks")


def test_search_merged_case(admin_client):
    c1 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Combined case",
        estate="?",
        point=Point(470267, 122766),
    )
    c2 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Merged case",
        estate="?",
        point=Point(470267, 122766),
    )
    c2.merge_into(c1)
    c2.save()
    resp = admin_client.get(f"/cases?search={c2.id}")
    assertContains(resp, "Merged case")


def test_user_ward_js_array(admin_client):
    resp = admin_client.get("/cases")
    assertContains(resp, "nw.user_wards = []")


def test_closed_cases(admin_client):
    open_case = Case.objects.create(
        closed=False,
    )
    closed_case = Case.objects.create(
        closed=True,
    )
    response = admin_client.get("/cases")
    assertContains(response, f"/cases/{open_case.id}")
    assertNotContains(response, f"/cases/{closed_case.id}")

    response = admin_client.get("/cases?closed=none")
    assertContains(response, f"/cases/{open_case.id}")
    assertNotContains(response, f"/cases/{closed_case.id}")

    response = admin_client.get("/cases?closed=include")
    assertContains(response, f"/cases/{open_case.id}")
    assertContains(response, f"/cases/{closed_case.id}")

    response = admin_client.get("/cases?closed=only")
    assertNotContains(response, f"/cases/{open_case.id}")
    assertContains(response, f"/cases/{closed_case.id}")


def test_priority_only_cases(admin_client, case_1, case_2):
    case_1.priority = True
    case_1.save()

    case_2.priority = False
    case_2.save()

    response = admin_client.get("/cases")
    assertContains(response, f"/cases/{case_1.id}")
    assertContains(response, f"/cases/{case_2.id}")

    response = admin_client.get("/cases?priority_only=on")
    assertContains(response, f"/cases/{case_1.id}")
    assertNotContains(response, f"/cases/{case_2.id}")


def _test_last_update_complaint_filter_includes_case(admin_client, case, expected):
    response = admin_client.get("/cases?last_update_was_complaint=on")
    url = f"/cases/{case.id}"
    if expected:
        assertContains(response, url)
    else:
        assertNotContains(response, url)


def test_last_update_was_complaint(admin_client, case_1, action_type):
    includes_case = partial(
        _test_last_update_complaint_filter_includes_case, admin_client, case_1
    )
    includes_case(False)

    action_1 = Action.objects.create(
        case=case_1,
        type=action_type,
    )
    includes_case(False)

    complaint_1 = Complaint.objects.create(
        case=case_1,
        happening_now=True,
    )
    includes_case(True)

    action_1.notes = "Arbitrary update."
    action_1.save()
    includes_case(True)

    Action.objects.create(
        case=case_1,
        type=action_type,
    )
    includes_case(False)

    complaint_1.description = "Arbitrary update."
    complaint_1.save()
    includes_case(False)

    Complaint.objects.create(
        case=case_1,
        happening_now=True,
    )
    includes_case(True)

    action_2 = Action.objects.create(
        case=case_1, type=action_type, time=case_1.modified - timedelta(minutes=1)
    )
    includes_case(True)

    action_2.time = case_1.modified + timedelta(minutes=1)
    action_2.save()
    includes_case(False)
