import re
from http import HTTPStatus

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from pytest_django.asserts import assertContains, assertNotContains

from accounts.models import User

from ..forms import ReassignForm
from ..models import Action, Case

pytestmark = pytest.mark.django_db


@pytest.fixture
def follow_perm(db):
    return Permission.objects.get(
        codename="follow", content_type=ContentType.objects.get_for_model(Case)
    )


@pytest.fixture
def get_assigned_perm(db):
    return Permission.objects.get(
        codename="get_assigned", content_type=ContentType.objects.get_for_model(Case)
    )


@pytest.fixture
def staff_user_1(db, follow_perm, get_assigned_perm):
    u = User.objects.create(is_staff=True, username="staffuser1")
    u.user_permissions.set([follow_perm, get_assigned_perm])
    u.save()
    return u


@pytest.fixture
def staff_user_2(db, follow_perm, get_assigned_perm):
    u = User.objects.create(
        is_staff=True, username="staffuser2", email="staffuser2@example.org"
    )
    u.user_permissions.set([follow_perm, get_assigned_perm])
    u.save()
    return u


@pytest.fixture
def no_perms_staff_user(db):
    return User.objects.create(
        is_staff=True,
        username="nopermstaff",
        email="nopermstaff@example.org",
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


def test_reassign_ward_list(admin_client, case_1, staff_user_1, staff_user_2):
    staff_user_2.wards = ["E05009372", case_1.ward]
    staff_user_2.save()
    response = admin_client.get(f"/cases/{case_1.id}/reassign")
    assert re.search(
        r'(?s)id="id_assigned_1"\s+value="'
        + str(staff_user_2.id)
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


def test_reassign_does_not_include_unassignable_staff(
    admin_client, case_1, staff_user_1, no_perms_staff_user
):
    response = admin_client.get(f"/cases/{case_1.id}/reassign")
    assertContains(response, staff_user_1.username)
    assertNotContains(response, no_perms_staff_user.username)


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


def test_following_requires_permission(client, case_1, no_perms_staff_user):
    client.force_login(no_perms_staff_user)
    response = client.post(
        f"/cases/{case_1.id}/follower-state",
        {"add": no_perms_staff_user.id},
        follow=True,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_unfollowing_does_not_require_permission(client, case_1, staff_user_1):
    case_1.followers.set([staff_user_1])
    case_1.save()
    client.force_login(staff_user_1)
    response = client.post(
        f"/cases/{case_1.id}/follower-state", {"remove": staff_user_1.id}, follow=True
    )
    assert response.status_code == HTTPStatus.OK
    case_1.refresh_from_db()
    assert len(case_1.followers.all()) == 0
