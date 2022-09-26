import datetime
from http import HTTPStatus
import re
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest
from django.template import Context, Template
from django.urls import reverse
from django.utils.timezone import make_aware, now
from pytest_django.asserts import assertContains, assertNotContains

from accounts.models import User

from ..forms import LogActionForm
from ..models import (
    Action,
    ActionFile,
    ActionType,
    Case,
    CaseSettingsSingleton,
    Complaint,
)
from ..views import compile_dates

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user_1(db):
    return User.objects.create(is_staff=True, username="staffuser1")


@pytest.fixture
def staff_user_2(db):
    return User.objects.create(is_staff=True, username="staffuser2")


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


@pytest.fixture
def logged_action_1(case_1, staff_user_1, action_types):
    return Action.objects.create(
        type=action_types[0],
        notes="internal notes",
        case=case_1,
        created_by=staff_user_1,
    )


@pytest.fixture
def case_other_uprn(db):
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {
            "string": "Flat 4, 2 Example Road, E8 2DP",
            "ward": "Hackney Central",
            "latitude": 51,
            "longitude": -0.1,
        }
        yield Case.objects.create(
            uprn=10001, kind="other", kind_other="Wombat", estate="y"
        )


@pytest.fixture
def case_bad_uprn(db):
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {"string": "", "ward": ""}
        yield Case.objects.create(uprn="bad_uprn", kind="diy", estate="?")


@pytest.fixture
def complaint(db, case_1, normal_user):
    return Complaint.objects.create(
        case=case_1,
        complainant=normal_user,
        happening_now=True,
        end=make_aware(datetime.datetime(2021, 11, 9, 14, 29)),
    )


@pytest.fixture
def action_types(db):
    return [
        ActionType.objects.create(name="Letter sent", common=True),
        ActionType.objects.create(name="Noise witnessed"),
        ActionType.objects.create(name="Abatement Notice “Section 80” served"),
    ]


def test_case_not_found(admin_client):
    response = admin_client.get("/cases/1")
    assertContains(response, "not be found", status_code=404)


def test_case(admin_client, case_1, complaint):
    response = admin_client.get(f"/cases/{case_1.id}")
    assertContains(response, "DIY")
    assertContains(response, "Normal User")
    assertContains(response, "Available weekends, by phone", html=True)


def test_case_uprn(admin_client, case_other_uprn):
    response = admin_client.get(f"/cases/{case_other_uprn.id}")
    assertContains(response, "Wombat")
    assertContains(response, "Flat 4, 2 Example Road")
    response = admin_client.get("/cases?uprn=10001")
    assertContains(response, "Flat 4, 2 Example Road")


def test_bad_uprn(admin_client, case_bad_uprn):
    response = admin_client.get(f"/cases/{case_bad_uprn.id}")
    assertContains(response, "DIY")
    assertContains(response, "bad_uprn")


def test_log_view(admin_client, case_1, action_types):
    response = admin_client.get(f"/cases/{case_1.id}/log")
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        {"notes": "", "type": action_types[0].id},
    )
    assertContains(response, "required")
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        {"notes": "Some notes", "type": action_types[0].id},
        follow=True,
    )
    response = admin_client.get("/cases?assigned=others")
    assertContains(response, "Letter sent")


def test_log_case_closure(admin_client, case_1, action_types):
    admin_client.post(
        f"/cases/{case_1.id}/log",
        {"notes": "Some notes", "type": ActionType.case_closed.id},
        follow=True,
    )
    case_1.refresh_from_db()
    assert case_1.closed


def test_log_case_reopening(admin_client, case_1, action_types):
    case_1.closed = True
    case_1.save()
    admin_client.post(
        f"/cases/{case_1.id}/log",
        {"notes": "Some notes", "type": ActionType.case_reopened.id},
        follow=True,
    )
    case_1.refresh_from_db()
    assert not case_1.closed


def test_log_form(case_1):
    form = LogActionForm(instance=case_1, data={"notes": "hmm"})
    assert form.errors["type"] == ["This field is required."]


def test_edit_logged_action_view(logged_action_1, client):
    new_notes = "edited: " + logged_action_1.notes

    client.force_login(logged_action_1.created_by)

    response = client.get(
        f"/cases/{logged_action_1.case.id}/log/{logged_action_1.id}/edit"
    )
    assert response.status_code == HTTPStatus.OK

    logged_action_1.created = now()
    logged_action_1.save()

    response = client.post(
        f"/cases/{logged_action_1.case.id}/log/{logged_action_1.id}/edit",
        {
            "notes": new_notes,
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    logged_action_1.refresh_from_db()
    assert logged_action_1.notes == new_notes


def test_edit_logged_action_forbidden_for_staff_who_didnt_log(
    logged_action_1, staff_user_2, client
):
    client.force_login(staff_user_2)

    logged_action_1.created = now()
    logged_action_1.save()

    response = client.post(
        f"/cases/{logged_action_1.case.id}/log/{logged_action_1.id}/edit",
        {
            "notes": logged_action_1.notes,
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_edit_logged_action_forbidden_after_edit_window(logged_action_1, client):
    window = CaseSettingsSingleton.instance.logged_action_editing_window

    client.force_login(logged_action_1.created_by)

    logged_action_1.created = now() - window
    logged_action_1.save()

    response = client.post(
        f"/cases/{logged_action_1.case.id}/log/{logged_action_1.id}/edit",
        {
            "notes": logged_action_1.notes,
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_edit_link_for_action_in_staff_case_view(
    logged_action_1, staff_user_1, staff_user_2, client
):
    case = logged_action_1.case

    logged_action_1.created = now()
    logged_action_1.save()

    client.force_login(staff_user_1)
    logged_action_1.created_by = staff_user_2
    logged_action_1.save()

    edit_link = 'href="%s"' % reverse(
        "case-edit-action", args=[case.id, logged_action_1.id]
    )

    response = client.get(f"/cases/{case.id}")
    assertNotContains(response, edit_link, status_code=HTTPStatus.OK)

    logged_action_1.created_by = staff_user_1
    logged_action_1.save()

    response = client.get(f"/cases/{case.id}")
    assertContains(response, edit_link, status_code=HTTPStatus.OK)

    logged_action_1.created = now() - (
        CaseSettingsSingleton.instance.logged_action_editing_window
        + datetime.timedelta(seconds=1)
    )
    logged_action_1.save()
    response = client.get(f"/cases/{case.id}")
    assertNotContains(response, edit_link, status_code=HTTPStatus.OK)


def test_action_output(
    admin_client, staff_user_1, staff_user_2, case_1, case_other_uprn, action_types
):
    a = Action(case=case_1, type=action_types[0], notes="Notes")
    assert str(a) == f"None, Letter sent, case {case_1.id}"
    a = Action(case=case_1, case_old=case_other_uprn)
    assert str(a) == f"None merged case {case_other_uprn.id} into case {case_1.id}"
    a = Action(case=case_1)
    assert str(a) == f"None, case {case_1.id}, unknown action"


def test_case_had_abatement(admin_client, case_1, action_types):
    assert not case_1.had_abatement_notice
    admin_client.post(
        f"/cases/{case_1.id}/log", {"notes": "Some notes", "type": action_types[2].id}
    )
    admin_client.post(
        f"/cases/{case_1.id}/log", {"notes": "Some notes", "type": action_types[1].id}
    )
    case_1 = Case.objects.get(id=case_1.id)  # Refresh to get rid of cached properties
    assert case_1.had_abatement_notice


def test_case_actions_reversed_is_sorted_by_time(case_1):
    a1 = Action.objects.create(case=case_1)
    the_past = now() - datetime.timedelta(days=1)
    a2 = Action.objects.create(case=case_1, time=the_past)
    assert list(case_1.actions_reversed) == [a1, a2]


def test_case_manager_prefetch_timeline_sorts_actions_by_time(case_1):
    a1 = Action.objects.create(case=case_1)
    the_past = now() - datetime.timedelta(days=1)
    a2 = Action.objects.create(case=case_1, time=the_past)
    Case.objects.prefetch_timeline([case_1])
    assert case_1.actions_reversed == [a1, a2]


def test_action_manager(case_1, case_other_uprn):
    a = Action.objects.create(case=case_1, case_old=case_other_uprn)
    merge_map = Action.objects.get_merged_cases([case_1])
    assert merge_map == {
        case_1.id: case_1.id,
        case_other_uprn.id: case_1.id,
    }
    Case.objects.prefetch_timeline([case_1])
    assert case_1.actions_reversed == [a]


def test_complaint_view(admin_client, complaint):
    response = admin_client.get(f"/cases/{complaint.case.id}/complaint/{complaint.id}")
    assertContains(response, "Still ongoing at Tue, 9 Nov 2021, 2:29 p.m.", html=True)


def test_complaint_bad_case(admin_client, case_other_uprn, complaint):
    response = admin_client.get(f"/cases/{case_other_uprn.id}/complaint/{complaint.id}")
    assert response.status_code == 302


def test_param_replace():
    request = HttpRequest()
    request.GET.update({"param": "value", "page": 10, "delete": "yes"})
    context = Context({"request": request})
    template = Template("{% load page_filter %}{% param_replace page=123 delete='' %}")
    rendered_template = template.render(context)
    assert rendered_template == "param=value&amp;page=123"

    request.GET.update({"ajax": 1})
    rendered_template = template.render(context)
    assert rendered_template == "param=value&amp;page=123"


def test_wfs_server_down(requests_mock):
    requests_mock.get(re.compile("point/27700"), json={})
    requests_mock.get(re.compile("greenspaces/ows"), text="Error")
    requests_mock.get(re.compile("transport/ows"), text="Error")
    requests_mock.get(re.compile("housing/ows"), text="Error")
    case = Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)
    assert case.location_display == "800m around (470267,122766)"


def test_compile_dates_correctly_uses_the_current_timezone():
    start_date = datetime.date(2000, 1, 9)
    start_time = datetime.time(10, 23, 46)
    end_time = datetime.time(14, 32, 54)
    data = {
        "start_date": start_date,
        "start_time": start_time,
        "end_time": end_time,
        "happening_now": False,
    }
    expected_start_naive = datetime.datetime(2000, 1, 9, 10, 23, 46)
    expected_start = make_aware(expected_start_naive)
    expected_end_naive = datetime.datetime(2000, 1, 9, 14, 32, 54)
    expected_end = make_aware(expected_end_naive)

    start, end = compile_dates(data)
    assert start == expected_start
    assert end == expected_end


def test_log_files_happy_path(admin_client, case_1, action_types):
    uploaded_files = [
        SimpleUploadedFile(fn, fn.encode(), content_type="text/plain")
        for fn in ["a_test_file.txt", "another_one.txt"]
    ]
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        {
            "notes": "notes",
            "type": action_types[0].id,
            "files": uploaded_files,
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    action = Action.objects.get(case=case_1)
    action_files = ActionFile.objects.filter(action=action).all()

    uploaded_file_to_action_file = {}
    for uploaded_file in uploaded_files:
        for action_file in action_files:
            if action_file.original_name == uploaded_file.name:
                uploaded_file_to_action_file[uploaded_file] = action_file

    for uploaded_file in uploaded_files:
        if uploaded_file not in uploaded_file_to_action_file.keys():
            pytest.fail(
                f"Couldn't find an ActionFile for uploaded file {uploaded_file.name}"
            )

    case_detail_response = admin_client.get(f"/cases/{case_1.id}")
    assert response.status_code == HTTPStatus.OK

    for uploaded_file, action_file in uploaded_file_to_action_file.items():
        action_file_url = action_file.get_absolute_url()
        assertContains(case_detail_response, 'href="%s"' % action_file_url)

        response = admin_client.get(action_file_url)
        assert response.status_code == HTTPStatus.OK
        assert response.getvalue() == uploaded_file.name.encode()


def test_non_staff_cant_access_logged_files(
    admin_client, client, case_1, action_types, normal_user
):
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        {
            "notes": "notes",
            "type": action_types[0].id,
            "files": [
                SimpleUploadedFile("test.txt", b"test", content_type="text/plain")
            ],
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    action = Action.objects.get(case=case_1)
    action_file = ActionFile.objects.get(action=action)

    client.force_login(normal_user)

    response = client.get(action_file.get_absolute_url())
    assert response.status_code != HTTPStatus.OK
