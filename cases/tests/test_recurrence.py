import datetime
from functools import partial
import pytest
from django.core import mail
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
    return Case.objects.create(
        kind="diy", created_by=normal_user, ward="outside", where="residence"
    )


@pytest.fixture
def complaint(db, case_1, normal_user):
    return Complaint.objects.create(
        case=case_1,
        complainant=normal_user,
        happening_now=True,
    )


@pytest.fixture
def staff_dest(settings):
    settings.COBRAND_SETTINGS["staff_destination"] = {
        "outside": "outside@example.org",
        "business": "business@example.org",
        "hackney-housing": "hh@example.org,hh2@example.org",
        "housing": "housing@example.org",
    }


def _post_step(client, case_1, step, data, **kwargs):
    return client.post(
        f"/cases/{case_1.id}/complaint/add/{step}",
        {f"recurrence_wizard_{case_1.id}-current_step": step, **data},
        **kwargs,
    )


def test_normal_user_permission(client, normal_user, complaint, settings):
    settings.NON_STAFF_ACCESS = True
    client.force_login(normal_user)
    resp = client.get(f"/cases/{complaint.case.id}/complaint/add")
    assert resp.status_code == 302
    complaint.delete()
    resp = client.get(f"/cases/{complaint.case.id}/complaint/add")
    assert resp.status_code == 404


def test_non_staff_normal_user_permission(client, normal_user, complaint, settings):
    settings.NON_STAFF_ACCESS = False
    client.force_login(normal_user)
    resp = client.get(f"/cases/{complaint.case.id}/complaint/add")
    assert resp.status_code == 302
    assert resp.url == "/"


def test_add_complaint_now_existing_user(admin_client, case_1, normal_user, staff_dest):
    post_step = partial(_post_step, admin_client, case_1)

    admin_client.get(f"/cases/{case_1.id}/complaint/add", follow=True)

    post_step("isitnow", {"isitnow-happening_now": "1"})
    post_step("isnow", {"isnow-start_date": "today", "isnow-start_time": "9pm"})
    post_step("isnow", {"isnow-start_date": "yesterday", "isnow-start_time": "9pm"})
    yesterday = datetime.date.today() - datetime.timedelta(days=1)

    post_step("rooms", {"rooms-rooms": "Room"})
    post_step("describe", {"describe-description": "Desc"})
    post_step("effect", {"effect-effect": "Effect"})

    post_step("user_search", {"user_search-search": "Normal User"})
    resp = post_step(
        "user_pick",
        {"user_pick-search": "Normal User", "user_pick-user": normal_user.id},
        follow=True,
    )
    assertContains(resp, f"{yesterday.strftime('%a, %-d %b %Y')}, 9 p.m.")
    assertContains(resp, "Still ongoing")
    assertContains(resp, "Normal User, 1 High Street")

    post_step("summary", {"summary-true_statement": 1}, follow=True)


def _test_add_complaint_not_now_new_user(
    admin_client, case_1, normal_user, user_data, state
):
    post_step = partial(_post_step, admin_client, case_1)

    case_1.closed = state
    case_1.save()

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
    params = {
        "user_pick-search": "Normal",
        "user_pick-user": 0,
        "user_pick-first_name": "Norman",
        "user_pick-last_name": "Normal",
    }
    resp = post_step(
        "user_pick", {**params, "user_pick-email": normal_user.email}, follow=True
    )
    assertContains(resp, "There is an existing user")
    resp = post_step("user_pick", {**params, **user_data}, follow=True)
    assertContains(resp, "Fri, 12 Nov 2021, 9 p.m.")
    assertContains(resp, "Fri, 12 Nov 2021, 10 p.m.")
    assertContains(resp, "Norman Normal")

    post_step("summary", {"summary-true_statement": 1}, follow=True)

    case_1.refresh_from_db()
    assert case_1.closed == False


def test_add_complaint_not_now_new_user_email(
    admin_client, case_1, normal_user, staff_dest
):
    _test_add_complaint_not_now_new_user(
        admin_client,
        case_1,
        normal_user,
        {"user_pick-email": "norman@example.org"},
        False,
    )


def test_add_complaint_not_now_new_user_phone(
    admin_client, case_1, normal_user, staff_dest
):
    _test_add_complaint_not_now_new_user(
        admin_client, case_1, normal_user, {"user_pick-phone": "07900000000"}, True
    )


def test_add_complaint_as_normal_user(
    client, complaint, normal_user, settings, staff_dest
):
    settings.NON_STAFF_ACCESS = True
    case = complaint.case
    post_step = partial(_post_step, client, case)

    client.force_login(normal_user)
    client.get(f"/cases/{case.id}/complaint/add")

    post_step("isitnow", {"isitnow-happening_now": "0"})
    post_step(
        "notnow",
        {
            "notnow-start_date_0": "12",
            "notnow-start_date_1": "11",
            "notnow-start_date_2": "2021",
            "notnow-start_time": "9pm",
            "notnow-end_time": "1am",
        },
    )

    post_step("rooms", {"rooms-rooms": "Room"})
    post_step("describe", {"describe-description": "Desc"})
    resp = post_step("effect", {"effect-effect": "Effect"}, follow=True)

    assertContains(resp, "Fri, 12 Nov 2021, 9 p.m.")
    assertContains(resp, "Sat, 13 Nov 2021, 1 a.m.")

    post_step("summary", {"summary-true_statement": 1}, follow=True)
    resp = client.get(f"/cases/{case.id}/complaint/add/summary", follow=True)

    assert len(mail.outbox) == 2
    email = mail.outbox[0]
    assert "noise reoccurrence" in email.body
    assert "Fri, 12 Nov 2021, 9 p.m." in email.body
    assert "Sat, 13 Nov 2021, 1 a.m." in email.body
    assert "1 High Street" in email.body
    assert "DIY" in email.body
    email = mail.outbox[1]
    assert "noise reoccurrence" in email.body
    assert "Fri, 12 Nov 2021, 9 p.m." in email.body
    assert "Sat, 13 Nov 2021, 1 a.m." in email.body
    assert "1 High Street" not in email.body
    assert "DIY" not in email.body
