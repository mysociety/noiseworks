import pytest
from pytest_django.asserts import assertContains
from accounts.models import User
from .models import Case
from .forms import ReassignForm

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user_1(db):
    return User.objects.create(is_staff=True, username="staffuser1")


@pytest.fixture
def staff_user_2(db):
    return User.objects.create(is_staff=True, username="staffuser2")


@pytest.fixture
def case_1(db, staff_user_1):
    return Case.objects.create(kind="diy", assigned=staff_user_1)


@pytest.fixture
def case_other_uprn(db):
    return Case.objects.create(uprn=10001, kind="other", kind_other="Wombat")


def test_list(admin_client, case_1):
    response = admin_client.get("/cases")
    assertContains(response, "Cases")


def test_assigned_filter(admin_client, admin_user, case_1):
    response = admin_client.get("/cases?assigned=others")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = admin_user
    case_1.save()
    response = admin_client.get("/cases")
    assertContains(response, f"/cases/{case_1.id}")
    case_1.assigned = None
    case_1.save()
    response = admin_client.get("/cases?assigned=none")
    assertContains(response, f"/cases/{case_1.id}")


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


def test_reassign():
    form = ReassignForm(data={})
    assert form.errors["assigned"] == ["This field is required."]


def test_reassign_bad_user(case_1, staff_user_1):
    form = ReassignForm(instance=case_1, data={"assigned": staff_user_1.id})
    assert form.errors["assigned"] == [
        "Select a valid choice. That choice is not one of the available choices."
    ]


def test_reassign_success(case_1, staff_user_2):
    form = ReassignForm(instance=case_1, data={"assigned": staff_user_2.id})
    assert form.is_valid()


def test_reassign_view(admin_client, case_1, staff_user_2):
    response = admin_client.get(f"/cases/{case_1.id}/reassign")
    assertContains(response, "staffuser2")
    response = admin_client.post(f"/cases/{case_1.id}/reassign", {"assigned": 0})
    assertContains(response, "valid choice")
    admin_client.post(f"/cases/{case_1.id}/reassign", {"assigned": staff_user_2.id})
