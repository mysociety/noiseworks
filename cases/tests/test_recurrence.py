import datetime
from functools import partial
import pytest
from pytest_django.asserts import assertContains
from accounts.models import User
from ..models import Case, Complaint

pytestmark = pytest.mark.django_db


@pytest.fixture
def normal_user(db):
    return User.objects.create(
        username="normal@example.org",
        email="normal@example.org",
        email_verified=True,
        phone="+447700900123",
        address="1 High Street",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def case_1(db, normal_user):
    return Case.objects.create(kind="diy", created_by=normal_user, ward="E05009373")


@pytest.fixture
def complaint(db, case_1, normal_user):
    return Complaint.objects.create(
        case=case_1,
        complainant=normal_user,
        happening_now=True,
    )


def _post_step(admin_client, case_1, step, data, **kwargs):
    return admin_client.post(
        f"/cases/{case_1.id}/complaint/add/{step}",
        {f"recurrence_wizard_{case_1.id}-current_step": step, **data},
        **kwargs,
    )


def test_normal_user_permission(client, normal_user, case_1, complaint):
    client.force_login(normal_user)
    resp = client.get(f"/cases/{case_1.id}/complaint/add")
    assert resp.status_code == 302
    complaint.delete()
    resp = client.get(f"/cases/{case_1.id}/complaint/add")
    assert resp.status_code == 404


def test_add_complaint_now_existing_user(admin_client, case_1, normal_user):
    post_step = partial(_post_step, admin_client, case_1)

    admin_client.get(f"/cases/{case_1.id}/complaint/add", follow=True)

    post_step("isitnow", {"isitnow-happening_now": "1"})
    post_step("isnow", {"isnow-start_date": "today", "isnow-start_time": "9pm"})
    post_step("isnow", {"isnow-start_date": "yesterday", "isnow-start_time": "9pm"})
    yesterday = datetime.date.today() - datetime.timedelta(days=1)

    post_step("rooms", {"rooms-rooms": "Room"})
    post_step("describe", {"describe-description": "Desc"})
    post_step("effect", {"effect-effect": "Effect"})

    post_step("user_search", {"user_search-search": "Normal"})
    resp = post_step(
        "user_pick",
        {"user_pick-search": "Normal", "user_pick-user": normal_user.id},
        follow=True,
    )
    assertContains(resp, f"{yesterday.strftime('%a, %d %b %Y')}, 9 p.m.")
    assertContains(resp, "Still ongoing")
    assertContains(resp, "Normal User, 1 High Street")

    post_step("summary", {"summary-true_statement": 1})

    admin_client.get(f"/cases/{case_1.id}/complaint/add/done")


def _test_add_complaint_not_now_new_user(admin_client, case_1, normal_user, user_data):
    post_step = partial(_post_step, admin_client, case_1)

    admin_client.get(f"/cases/{case_1.id}/complaint/add")

    post_step("isitnow", {"isitnow-happening_now": "0"})
    post_step("notnow", {})  # Test blank date submission
    post_step(
        "notnow",
        {
            "notnow-start_date_0": "100",
            "notnow-start_date_1": "12",
            "notnow-start_date_2": "2021",
        },
    )  # Test bad date submission
    post_step(
        "notnow",
        {
            "notnow-start_date_0": "12",
            "notnow-start_date_1": "11",
            "notnow-start_date_2": "2021",
            "notnow-start_time": "9pm",
            "notnow-end_time": "10pm",
        },
    )

    post_step("rooms", {"rooms-rooms": "Room"})
    post_step("describe", {"describe-description": "Desc"})
    post_step("effect", {"effect-effect": "Effect"})

    post_step("user_search", {"user_search-search": "Normal"})

    resp = post_step("user_pick", {"user_pick-search": "Normal", "user_pick-user": 0})
    assertContains(resp, "Please specify a name")
    resp = post_step(
        "user_pick",
        {
            "user_pick-search": "Normal",
            "user_pick-user": 0,
            "user_pick-first_name": "Norman",
            "user_pick-last_name": "Normal",
            **user_data,
        },
        follow=True,
    )
    assertContains(resp, "Fri, 12 Nov 2021, 9 p.m.")
    assertContains(resp, "Fri, 12 Nov 2021, 10 p.m.")
    assertContains(resp, "Norman Normal")

    post_step("summary", {"summary-true_statement": 1})
    admin_client.get(f"/cases/{case_1.id}/complaint/add/done")


def test_add_complaint_not_now_new_user_email(admin_client, case_1, normal_user):
    _test_add_complaint_not_now_new_user(
        admin_client, case_1, normal_user, {"user_pick-email": "norman@example.org"}
    )


def test_add_complaint_not_now_new_user_phone(admin_client, case_1, normal_user):
    _test_add_complaint_not_now_new_user(
        admin_client, case_1, normal_user, {"user_pick-phone": "07900000000"}
    )
