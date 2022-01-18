import pytest
from pytest_django.asserts import assertContains
from accounts.models import User
from ..models import Case

pytestmark = pytest.mark.django_db


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
        address="Address, London",
        email="normal2@example.org",
        email_verified=True,
        first_name="Normal",
        last_name="User2",
    )


@pytest.fixture
def case_1(db, normal_user):
    return Case.objects.create(kind="diy", created_by=normal_user, ward="E05009373")


def test_bad_submissions(admin_client, case_1, normal_user, normal_user_2):
    resp = admin_client.post(f"/cases/{case_1.id}/add-perpetrator")
    assert resp.status_code == 403
    resp = admin_client.post(
        f"/cases/{case_1.id}/add-perpetrator", {"search": "normal", "user": 0}
    )
    assertContains(resp, "Please specify a name and at least one")


def test_add_perpetrator(admin_client, case_1, normal_user, normal_user_2):
    admin_client.get(f"/cases/{case_1.id}/search-perpetrator")
    resp = admin_client.post(
        f"/cases/{case_1.id}/search-perpetrator", {"search": "normal"}
    )
    assertContains(resp, "Normal User2")
    admin_client.post(
        f"/cases/{case_1.id}/add-perpetrator",
        {"search": "normal", "user": normal_user.id},
    )
    params = {"search": "normal", "user": 0, "first_name": "Normal"}
    resp = admin_client.post(
        f"/cases/{case_1.id}/add-perpetrator",
        {**params, "last_name": "User2", "email": "normal2@example.org"},
        follow=True,
    )
    assertContains(resp, "There is an existing user")
    admin_client.post(
        f"/cases/{case_1.id}/add-perpetrator",
        {**params, "last_name": "User3", "email": "normal3@example.org"},
    )
    admin_client.post(
        f"/cases/{case_1.id}/add-perpetrator",
        {**params, "last_name": "User4", "phone": "07900000000"},
    )


def test_remove_perpetrator(admin_client, case_1, normal_user_2):
    admin_client.get(f"/cases/{case_1.id}/remove-perpetrator/{normal_user_2.id}")
