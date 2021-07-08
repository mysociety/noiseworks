import re
from unittest.mock import patch
import pytest
from pytest_django.asserts import assertContains
from sesame.tokens import create_token
from .models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(is_staff=True, username="foo@example.org")


def test_create_phone_user():
    user = User.objects.create_user(is_staff=True, username="0121 496 0000")
    assert user.phone_verified
    assert not user.email_verified


def test_bad_token(client):
    client.get(f"/a/badtoken")
    # And a token that is valid but for a user that does not exist
    user = User(id=1, username="foo@example.org")
    token = create_token(user)
    client.get(f"/a/{token}")


def test_staff_logging_in_by_token(client, staff_user):
    response = client.post("/a", {"username": "foo@example.org"})
    assert response.status_code == 403


def test_log_in_by_link_email(client):
    response = client.post("/a", {"username": "foo"})
    assertContains(response, "Enter a valid email address")
    response = client.post("/a", {"username": "foo@example.org"})
    assertContains(response, "Please check your")
    # Check email here once working!
    m = re.search(rb"Token is (.*?)\.", response.content)
    token = m.group(1).decode("ascii")
    response = client.get(f"/a/{token}")
    assert response.status_code == 302


@patch("phonenumber_field.phonenumber.PhoneNumber.is_valid")
def test_log_in_by_link_phone(is_valid, client):
    is_valid.return_value = True
    response = client.post("/a", {"username": "0121 496 0000"})
    assertContains(response, "Please provide a mobile number")
    with patch("phonenumber_field.phonenumber.PhoneNumber.is_mobile") as is_mobile:
        is_mobile.return_value = True
        response = client.post("/a", {"username": "07700 900000"})
    # Check text here once working!
    m = re.search(rb"Token is (.*?)\.", response.content)
    token = m.group(1).decode("ascii")
    response = client.get(f"/a/{token}")
    assert response.status_code == 302
