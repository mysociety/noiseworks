import re

import pytest
from django.core import mail
from pytest_django.asserts import assertContains, assertNotContains

from accounts.models import User

from ..forms import ReassignForm
from ..models import Action, Case

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user_1(db):
    return User.objects.create(is_staff=True, username="staffuser1")


@pytest.fixture
def staff_user_2(db):
    return User.objects.create(
        is_staff=True, username="staffuser2", email="staffuser2@example.org"
    )


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
def case_1(db, staff_user_1, normal_user):
    return Case.objects.create(
        kind="diy", assigned=staff_user_1, created_by=normal_user, ward="E05009373"
    )


def test_reassign():
    form = ReassignForm(data={})
    assert form.errors["assigned"] == ["This field is required."]


def test_reassign_same_user(case_1, staff_user_1):
    form = ReassignForm(instance=case_1, data={"assigned": staff_user_1.id})
    form.save()
    assert Action.objects.count() == 0


def test_reassign_success(case_1, staff_user_2):
    form = ReassignForm(instance=case_1, data={"assigned": staff_user_2.id})
    assert form.is_valid()


def test_reassign_ward_list(admin_client, admin_user, case_1, staff_user_1):
    admin_user.wards = ["E05009372", case_1.ward]
    admin_user.save()
    response = admin_client.get(f"/cases/{case_1.id}/reassign")
    assert re.search(
        r'(?s)id="id_assigned_1"\s+value="'
        + str(admin_user.id)
        + r'".*?<div class="govuk-radios__divider">or</div>.*?id="id_assigned_2"\s+value="'
        + str(staff_user_1.id)
        + '"',
        response.content.decode("utf-8"),
    )


def test_reassign_view(admin_client, case_1, staff_user_2):
    response = admin_client.get(f"/cases/{case_1.id}/reassign")
    assertContains(response, "staffuser2")
    response = admin_client.post(f"/cases/{case_1.id}/reassign", {"assigned": 0})
    assertContains(response, "valid choice")
    admin_client.post(f"/cases/{case_1.id}/reassign", {"assigned": staff_user_2.id})
    assert f"You have been assigned to case #{case_1.id}" in mail.outbox[0].body


def test_reassign_view_to_yourself(client, case_1):
    client.force_login(case_1.assigned)
    client.post(f"/cases/{case_1.id}/reassign", {"assigned": case_1.assigned.id})
    assert not len(mail.outbox)


def test_followers(admin_client, admin_user, case_1, staff_user_2):
    admin_user.wards = [case_1.ward]
    admin_user.save()
    response = admin_client.get(f"/cases/{case_1.id}")
    assertNotContains(response, "staffuser2")
    response = admin_client.get(f"/cases/{case_1.id}/followers")
    assertContains(response, "staffuser2")
    response = admin_client.post(
        f"/cases/{case_1.id}/followers", {"followers": staff_user_2.id}, follow=True
    )
    assertContains(response, "staffuser2")
    # Dummy so it counts as a POST with some data (CSRF token would be there normally)
    response = admin_client.post(
        f"/cases/{case_1.id}/followers", {"dummy": "1"}, follow=True
    )
    assertNotContains(response, "staffuser2")


def test_follower_buttons(admin_client, case_1):
    response = admin_client.get(f"/cases/{case_1.id}/follower-state")
    assert response.status_code == 403
    response = admin_client.get(f"/cases/{case_1.id}")
    assertNotContains(response, "admin")
    response = admin_client.post(
        f"/cases/{case_1.id}/follower-state", {"add": 1}, follow=True
    )
    assertContains(response, "admin")
    response = admin_client.post(
        f"/cases/{case_1.id}/follower-state", {"remove": 1}, follow=True
    )
    assertNotContains(response, "admin")
