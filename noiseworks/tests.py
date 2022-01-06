from pytest_django.asserts import assertContains
from django.conf import settings
from django.http import HttpRequest
from django.utils.module_loading import import_string
from accounts.models import User


def test_home_public(client):
    response = client.get("/")
    assert response.url == "/cases/add"


def test_home_staff(admin_client):
    response = admin_client.get("/")
    assert response.url == "/cases"


def test_home_unapproved_hackney(client, db):
    user = User.objects.create(email="foo@hackney.gov.uk")
    client.force_login(user)
    response = client.get("/")
    assertContains(response, "Please contact")


def test_home_logged_in(client, db):
    user = User.objects.create(email="foo@example.org")
    client.force_login(user)
    response = client.get("/")
    assert response.url == "/cases"


def test_setting_masking():
    request = HttpRequest()
    request.META = {"DATABASE_URL": "postgis://username:password@host/db"}
    Filter = import_string(settings.DEFAULT_EXCEPTION_REPORTER_FILTER)
    s = Filter().get_safe_request_meta(request)["DATABASE_URL"]
    assert "password" not in s
