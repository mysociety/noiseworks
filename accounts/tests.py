import re
from unittest.mock import mock_open, patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.management import CommandError, call_command
from pytest_django.asserts import assertContains
from sesame.tokens import create_token

from .forms import CodeForm
from .models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def normal_user(db):
    return User.objects.create_user(email="user@example.org")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        is_staff=True, email="foo@example.org", wards=["E05009374"]
    )


@pytest.fixture
def sms_catcher(requests_mock):
    sms_outbox = []

    def catch_sms(request, context):
        sent = request.json()
        sms_outbox.append(sent)
        return {}

    requests_mock.post(
        "https://api.notifications.service.gov.uk/v2/notifications/sms",
        status_code=201,
        json=catch_sms,
    )
    return sms_outbox


@pytest.fixture
def non_staff_access(settings):
    settings.NON_STAFF_ACCESS = True


@pytest.fixture
def only_staff_access(settings):
    settings.NON_STAFF_ACCESS = False


def test_create_user_without_email_or_phone():
    user = User.objects.create_user(
        first_name="No", last_name="Contact", address="Address"
    )
    assert user.id


def test_create_phone_user():
    user = User.objects.create_user(is_staff=True, phone="0121 496 0000")
    assert user.phone_verified
    assert not user.email_verified


def test_bad_token(client):
    client.get("/a/badtoken")
    # And a token that is valid but for a user that does not exist
    user = User(id=1, email="foo@example.org")
    token = create_token(user)
    client.get(f"/a/{token}")


def test_access_to_sign_in_page(client, only_staff_access):
    response = client.get("/a")
    assert response.status_code == 302


def test_staff_logging_in_by_token(client, staff_user, non_staff_access):
    response = client.post("/a", {"username": "Foo@example.org"})
    assert response.status_code == 403


def test_log_in_by_link_email(client, non_staff_access):
    response = client.post("/a", {"username": "foo"})
    assertContains(response, "Enter a valid email address")
    response = client.post("/a", {"username": "foo@example.org"})
    assertContains(response, "Please check your")
    m = re.search(r"(http[^\s]*)", mail.outbox[0].body)
    url = m.group(1)
    response = client.get(url)
    assert response.status_code == 302


@patch("phonenumber_field.phonenumber.PhoneNumber.is_valid")
def test_log_in_by_link_phone(
    is_valid, client, sms_catcher, settings, non_staff_access
):
    is_valid.return_value = True
    settings.NOTIFY_API_KEY = (
        "hey-968e4931-c77f-442d-b306-9c062e0e4787-745ae299-aad9-4de6-9ce1-df4d547f6b92"
    )

    response = client.post("/a", {"username": "0121 496 0000"})
    assertContains(response, "Please provide a mobile number")
    with patch("phonenumber_field.phonenumber.PhoneNumber.is_mobile") as is_mobile:
        is_mobile.return_value = True
        response = client.post("/a", {"username": "07700 900000"})
    m = re.search(r"(http[^\s]*)", sms_catcher[0]["personalisation"]["text"])
    url = m.group(1)
    response = client.get(url)
    assert response.status_code == 302


def test_log_in_by_code_errors(client):
    form = CodeForm({"user_id": "123", "code": "bad"})
    assert form.errors == {
        "user_id": ["Bad request"],
        "timestamp": ["This field is required."],
    }
    form = CodeForm({"user_id": "123", "code": "99999999999", "timestamp": "!!!"})
    assert form.errors == {
        "user_id": ["Bad request"],
    }


def test_log_in_by_code(client, non_staff_access):
    email = "foo@example.org"
    response = client.post("/a", {"username": email})
    assertContains(response, "Please check your")
    m = re.search(b'timestamp[^>]*value="([^"]*)"', response.content)
    timestamp = m.group(1).decode()
    m = re.search(b'user_id[^>]*value="([^"]*)"', response.content)
    user_id = m.group(1).decode()
    m = re.search(r"sign in token is ([^\s]*)", mail.outbox[0].body)
    code = m.group(1)
    response = client.post(
        "/a/code", {"user_id": user_id, "timestamp": timestamp, "code": "bad"}
    )
    response = client.post(
        "/a/code", {"user_id": user_id, "timestamp": timestamp, "code": code.title()}
    )
    assert response.status_code == 302


def test_user_adding(client, staff_user):
    client.force_login(staff_user)
    response = client.get("/a/add")
    assert response.status_code == 403

    permission = Permission.objects.get(
        codename="add_user", content_type=ContentType.objects.get_for_model(User)
    )
    staff_user.user_permissions.add(permission)
    client.get("/a/add")
    response = client.post(
        "/a/add",
        {
            "first_name": "New",
            "last_name": "User",
            "email": "foo2@example.org",
            "wards": ["E05009378", "E05009374"],
        },
    )
    assert response.status_code == 302
    assert response.url == "/a/list"
    user = User.objects.get(email="foo2@example.org", email_verified=True)
    assert user.is_staff


def test_basic_user_editing(client, staff_user, normal_user):
    client.force_login(staff_user)
    response = client.get("/a/list")
    response = client.get(f"/a/{normal_user.id}/edit")
    response = client.post(
        f"/a/{normal_user.id}/edit",
        {"best_time": ["weekday", "evening"], "best_method": "email"},
    )
    assert response.status_code == 302
    assert response.url == "/a/list"


def test_staff_user_editing_by_staff(client, staff_user):
    client.force_login(staff_user)
    response = client.get(f"/a/{staff_user.id}/edit")
    assert response.status_code == 403


def test_staff_user_editing(client, staff_user):
    permission = Permission.objects.get(
        codename="change_user", content_type=ContentType.objects.get_for_model(User)
    )
    staff_user.user_permissions.add(permission)
    client.force_login(staff_user)
    client.get(f"/a/{staff_user.id}/edit")
    response = client.post(
        f"/a/{staff_user.id}/edit",
        {
            "first_name": "Staff",
            "last_name": "User",
            "email": "foo@example.org",
            "wards": ["E05009378", "E05009374"],
        },
    )
    assert response.status_code == 302
    assert response.url == "/a/list"


def test_staff_user_existing(admin_client, staff_user, normal_user):
    response = admin_client.post(
        f"/a/{staff_user.id}/edit",
        {
            "first_name": "S",
            "last_name": "U",
            "email": normal_user.email,
            "phone": "07900000000",
            "phone_verified": "1",
        },
    )
    assertContains(response, "user with this email address already")


def test_staff_user_existing_phone(admin_client, staff_user, normal_user):
    normal_user.phone_verified = True
    normal_user.phone = "07900000000"
    normal_user.save()
    response = admin_client.post(
        f"/a/{staff_user.id}/edit",
        {
            "first_name": "S",
            "last_name": "U",
            "email": staff_user.email,
            "phone": "07900000000",
            "phone_verified": "1",
        },
    )
    assertContains(response, "user with this phone number already")


def test_edit_redirect_back_to_case(admin_client, staff_user):
    response = admin_client.post(
        f"/a/{staff_user.id}/edit?case=123",
        {
            "first_name": "Staff",
            "last_name": "User",
            "email": "foo@example.org",
            "wards": ["E05009378", "E05009374"],
        },
    )
    assert response.status_code == 302
    assert response.url == "/cases/123"


def test_address_display_uprn():
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {
            "string": "Flat 4, 2 Example Road, E8 2DP",
            "ward": "Hackney Central",
            "latitude": 51,
            "longitude": -0.1,
        }
        user = User.objects.create(first_name="Norma", last_name="User", uprn=10001)
        assert user.address_display == "Flat 4, 2 Example Road, E8 2DP"


def test_address_display_uprn_no_data():
    with patch("cobrand_hackney.api.address_for_uprn") as address_for_uprn:
        address_for_uprn.return_value = {"string": "", "ward": ""}
        user = User.objects.create(first_name="Norma", last_name="User", uprn=10001)
        assert user.address_display == 10001


def test_address_display_address():
    user = User.objects.create(
        first_name="Norma", last_name="User", address="Other address", uprn=10001
    )
    assert user.address_display == "Other address"
    assert str(user) == "Norma User, Other address"


def test_sign_out(client):
    resp = client.get("/a/sign-out")
    assertContains(resp, "signed out")


def test_add_staff_command(db, capsys, monkeypatch):
    with pytest.raises(CommandError):
        call_command("add_staff_users")

    data_dict = {
        "bad.csv": "Name,Email,Wards\nTest Test,test1@example.org,Bad Ward\n",
        "good.csv": "Name,Email,Wards\nTest Test,test2@example.org\nTester McTest,test3@example.org,Hackney Central|Victoria",
        "goodmap.csv": "Name,Email,Wards\nTest Test,test2@example.org\nTest Test,test4@example.org,North",
        "mapping.csv": "Name,Ward\nNorth,Hackney Central\nNorth,Stoke Newington",
    }

    def open_side_effect(name):
        return mock_open(read_data=data_dict.get(name))()

    monkeypatch.setattr("builtins.open", open_side_effect)

    with pytest.raises(CommandError):
        call_command("add_staff_users", csv_file="bad.csv")

    call_command("add_staff_users", csv_file="good.csv")
    assert User.objects.count() == 0, "no change in users without commit"
    call_command("add_staff_users", csv_file="good.csv", commit=True)
    user = User.objects.get(email="test2@example.org")
    assert user.first_name == "Test"
    assert user.is_staff
    user = User.objects.get(email="test3@example.org")
    assert user.wards == ["E05009372", "E05009386"]

    call_command(
        "add_staff_users",
        csv_file="goodmap.csv",
        ward_mapping="mapping.csv",
        commit=True,
    )
    output = capsys.readouterr()
    assert "test2@example.org already exists" in output.out
    assert "test4@example.org" in output.out
    user = User.objects.get(email="test4@example.org")
    assert user.wards == ["E05009372", "E05009385"]
