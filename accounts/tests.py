import re
import uuid
from unittest.mock import patch
import pytest
from pytest_django.asserts import assertContains
from django.core import mail
from django.test import override_settings
from sesame.tokens import create_token
from .models import User
from .forms import CodeForm

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(is_staff=True, email="foo@example.org")


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
    client.get(f"/a/badtoken")
    # And a token that is valid but for a user that does not exist
    user = User(id=1, email="foo@example.org")
    token = create_token(user)
    client.get(f"/a/{token}")


@override_settings(NON_STAFF_ACCESS=False)
def test_access_to_sign_in_page(client):
    response = client.get("/a")
    assert response.status_code == 302


@override_settings(NON_STAFF_ACCESS=True)
def test_staff_logging_in_by_token(client, staff_user):
    response = client.post("/a", {"username": "foo@example.org"})
    assert response.status_code == 403


@override_settings(NON_STAFF_ACCESS=True)
def test_log_in_by_link_email(client):
    response = client.post("/a", {"username": "foo"})
    assertContains(response, "Enter a valid email address")
    response = client.post("/a", {"username": "foo@example.org"})
    assertContains(response, "Please check your")
    m = re.search(r"(http[^\s]*)", mail.outbox[0].body)
    url = m.group(1)
    response = client.get(url)
    assert response.status_code == 302


@override_settings(NON_STAFF_ACCESS=True)
@patch("phonenumber_field.phonenumber.PhoneNumber.is_valid")
def test_log_in_by_link_phone(is_valid, client, sms_catcher, settings):
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


def test_log_in_by_code(client):
    email = "foo@example.org"
    response = client.post("/a", {"username": email})
    assertContains(response, "Please check your")
    m = re.search(b'timestamp[^>]*value="([^"]*)"', response.content)
    timestamp = m.group(1).decode()
    m = re.search(b'user_id[^>]*value="([^"]*)"', response.content)
    user_id = m.group(1).decode()
    m = re.search(r"Or enter this token: ([^\s]*)", mail.outbox[0].body)
    code = m.group(1)
    response = client.post(
        "/a/code", {"user_id": user_id, "timestamp": timestamp, "code": "bad"}
    )
    response = client.post(
        "/a/code", {"user_id": user_id, "timestamp": timestamp, "code": code}
    )
    assert response.status_code == 302


def test_basic_user_editing(admin_client, staff_user):
    response = admin_client.get("/a/list")
    response = admin_client.get(f"/a/{staff_user.id}/edit")
    response = admin_client.post(
        f"/a/{staff_user.id}/edit",
        {
            "best_time": ["weekday", "evening"],
            "wards": ["E05009378", "E05009374"],
            "best_method": "email",
        },
    )
    assert response.status_code == 302


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
