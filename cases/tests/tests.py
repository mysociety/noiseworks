import datetime
import re
from unittest.mock import patch
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.template import Context, Template
from django.http import HttpRequest
from django.utils.timezone import make_aware
from accounts.models import User
from ..models import Case, Complaint, ActionType, Action
from ..forms import ReassignForm, ActionForm

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
def case_other_uprn(db):
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {
            "string": "Flat 4, 2 Example Road, E8 2DP",
            "ward": "Hackney Central",
            "latitude": 51,
            "longitude": -0.1,
        }
        yield Case.objects.create(uprn=10001, kind="other", kind_other="Wombat")


@pytest.fixture
def case_bad_uprn(db):
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {"string": "", "ward": ""}
        yield Case.objects.create(uprn="bad_uprn", kind="diy")


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
    ]


def test_case_not_found(admin_client):
    response = admin_client.get("/cases/1")
    assertContains(response, "Not Found", status_code=404)


def test_case(admin_client, case_1, complaint):
    response = admin_client.get(f"/cases/{case_1.id}")
    assertContains(response, "DIY")
    assertContains(response, "Normal User")
    assertContains(response, "Available weekends, by phone", html=True)


def test_case_uprn(admin_client, case_other_uprn):
    response = admin_client.get(f"/cases/{case_other_uprn.id}")
    assertContains(response, "Wombat")
    assertContains(response, "Flat 4, 2 Example Road")
    response = admin_client.get(f"/cases?assigned=&uprn=10001")
    assertContains(response, "Flat 4, 2 Example Road")


def test_bad_uprn(admin_client, case_bad_uprn):
    response = admin_client.get(f"/cases/{case_bad_uprn.id}")
    assertContains(response, "DIY")
    assertContains(response, "bad_uprn")


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
    response = admin_client.get(f"/cases?assigned=others")
    assertContains(response, "Letter sent")


def test_log_form(case_1):
    form = ActionForm(instance=case_1, data={"notes": "hmm"})
    assert form.errors["type"] == ["This field is required."]


def test_action_output(
    admin_client, staff_user_1, staff_user_2, case_1, case_other_uprn, action_types
):
    a = Action(case=case_1, type=action_types[0], notes="Notes")
    assert str(a) == f"None, Letter sent, case {case_1.id}"
    a = Action(case=case_1, case_old=case_other_uprn)
    assert str(a) == f"None merged case {case_other_uprn.id} into case {case_1.id}"
    a = Action(case=case_1)
    assert str(a) == f"None, case {case_1.id}, unknown action"


def test_merging_cases(admin_client, case_1, case_other_uprn, action_types):
    response = admin_client.post(
        f"/cases/{case_other_uprn.id}/merge", {"stop": 1}, follow=True
    )
    assertNotContains(response, "We have forgotten your current merging.")
    response = admin_client.post(f"/cases/{case_other_uprn.id}/merge")
    assertContains(response, "Select a case to merge into")
    response = admin_client.get(f"/cases/{case_1.id}")
    assertContains(response, f"Merge #{case_other_uprn.id} into this case")
    response = admin_client.post(
        f"/cases/{case_other_uprn.id}/merge", {"stop": 1}, follow=True
    )
    assertContains(response, "We have forgotten your current merging.")
    assertNotContains(response, "Merge #{case_other_uprn.id} into this case")
    response = admin_client.post(f"/cases/{case_other_uprn.id}/merge")
    response = admin_client.post(f"/cases/{case_1.id}/merge", {"dupe": 1}, follow=True)
    assertContains(response, "has been merged into")

    a = Action.objects.create(case=case_1, notes="Internal note", type=action_types[1])

    response = admin_client.get(f"/cases/{case_other_uprn.id}")
    assertContains(response, "This case has been merged into")
    assertContains(response, "Noise witnessed")


def test_action_manager(case_1, case_other_uprn):
    a = Action.objects.create(case=case_1, case_old=case_other_uprn)
    merge_map = Action.objects.get_merged_cases([case_1])
    assert merge_map == {
        case_1.id: case_1.id,
        case_other_uprn.id: case_1.id,
    }
    actions = Action.objects.get_reversed(merge_map)
    assert actions == {case_1.id: [a]}


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
