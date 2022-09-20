from functools import partial

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


def _post_step(client, case_1, step, data, **kwargs):
    data = {f"{step}-{k}": v for k, v in data.items()}
    return client.post(
        f"/cases/{case_1.id}/perpetrator/add/{step}",
        {f"perpetrator_wizard_{case_1.id}-current_step": step, **data},
        **kwargs,
    )


def test_bad_submissions(admin_client, case_1, normal_user, normal_user_2):
    post_step = partial(_post_step, admin_client, case_1)
    resp = post_step("user_search", {"search": "normal"})
    resp = post_step("user_pick", {"user": 0}, follow=True)
    assertContains(resp, "Please specify a name and at least one")


def test_add_perpetrator(
    admin_client, case_1, normal_user, normal_user_2, address_lookup
):
    post_step = partial(_post_step, admin_client, case_1)
    resp = admin_client.get(f"/cases/{case_1.id}/perpetrator/add", follow=True)
    resp = post_step("user_search", {"search": "normal"}, follow=True)
    assertContains(resp, "Normal User2")
    post_step("user_pick", {"user": normal_user.id}, follow=True)
    resp = post_step("user_search", {"search": "notexisting"}, follow=True)
    resp = post_step(
        "user_pick",
        {
            "user": 0,
            "first_name": "Normal",
            "last_name": "User2",
            "email": "normal2@example.org",
        },
        follow=True,
    )
    assertContains(resp, "There is an existing user")
    assertContains(resp, "Normal User2")
    params = {"user": 0, "first_name": "Normal"}
    resp = post_step(
        "user_pick",
        {
            **params,
            "last_name": "User3",
            "email": "normal3@example.org",
            "postcode": "E8 3DY",
        },
        follow=True,
    )
    post_step("user_pick", {**params, "last_name": "User4", "phone": "07900000000"})


def test_remove_perpetrator(admin_client, case_1, normal_user_2):
    admin_client.get(f"/cases/{case_1.id}/remove-perpetrator/{normal_user_2.id}")
