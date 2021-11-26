import datetime
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.test import override_settings
from django.utils.timezone import make_aware
from accounts.models import User
from ..models import Case, Complaint, ActionType, Action

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user_1(db):
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
def normal_user_2(db):
    return User.objects.create(
        username="normal2@example.org",
        email="normal2@example.org",
        email_verified=True,
        first_name="Normal",
        last_name="User2",
    )


@pytest.fixture
def case_1(db, normal_user):
    return Case.objects.create(
        kind="diy",
        location_cache="Entered location",
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def edited_case(db, case_1):
    case_1.location_cache = "Staff edited location"
    case_1.save()
    return case_1


@pytest.fixture
def complaint(db, case_1, normal_user):
    return Complaint.objects.create(
        case=case_1,
        complainant=normal_user,
        happening_now=True,
        end=make_aware(datetime.datetime(2021, 11, 9, 14, 29)),
    )


@pytest.fixture
def action_types(case_1):
    at0 = ActionType.objects.create(
        name="Letter sent", common=True, visibility="public"
    )
    at1 = ActionType.objects.create(name="Noise witnessed")
    Action.objects.create(case=case_1, notes="Internal note", type=at0)
    Action.objects.create(case=case_1, notes="Internal note", type=at1)


@override_settings(NON_STAFF_ACCESS=True)
def test_case_list_user_view(client, complaint, edited_case):
    client.force_login(complaint.complainant)
    response = client.get("/cases")
    assertContains(response, "DIY")
    assertContains(response, "Entered location")
    assertNotContains(response, "Staff edited location")


@override_settings(NON_STAFF_ACCESS=True)
def test_case_detail_user_view(client, complaint, action_types):
    client.force_login(complaint.complainant)
    response = client.get(f"/cases/{complaint.case.id}")
    assertContains(response, "Letter sent")
    assertNotContains(response, "Noise witnessed")


@override_settings(NON_STAFF_ACCESS=True)
def test_case_detail_user_view_assignment(client, complaint, staff_user_1):
    complaint.case.assigned = staff_user_1
    complaint.case.save()
    client.force_login(complaint.complainant)
    response = client.get(f"/cases/{complaint.case.id}")
    assertContains(response, "Case assigned to officer")
    assertNotContains(response, "staffuser1")


@override_settings(NON_STAFF_ACCESS=True)
def test_case_details_other_user_view(client, case_1, normal_user_2):
    client.force_login(normal_user_2)
    response = client.get(f"/cases/{case_1.id}")
    assert response.status_code == 404


@override_settings(NON_STAFF_ACCESS=True)
def test_case_location_display(client, complaint, edited_case):
    client.force_login(complaint.complainant)
    response = client.get(f"/cases/{edited_case.id}")
    assertContains(response, "Entered location")
    assertNotContains(response, "Staff edited location")


@override_settings(NON_STAFF_ACCESS=False)
def test_non_staff_case_list_user_view(client, normal_user):
    client.force_login(normal_user)
    response = client.get("/cases")
    assert response.status_code == 302


@override_settings(NON_STAFF_ACCESS=False)
def test_non_staff_case_detail_user_view(client, normal_user, case_1):
    client.force_login(normal_user)
    response = client.get(f"/cases/{case_1.id}")
    assert response.status_code == 302


@override_settings(NON_STAFF_ACCESS=False)
def test_non_staff_complaint_view(client, normal_user, complaint):
    client.force_login(normal_user)
    response = client.get(f"/cases/{complaint.case.id}/complaint/{complaint.id}")
    assert response.status_code == 302
