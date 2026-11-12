import pytest
from django.conf import settings
from django.http import HttpRequest
from django.utils.module_loading import import_string
from pytest_django.asserts import assertContains

from accounts.models import User
from noiseworks.views import server_error


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(is_staff=True, email="foo@example.org")


def test_home_public(client):
    response = client.get("/")
    assert response.url == "/cases/add"


def test_home_staff(admin_client):
    response = admin_client.get("/")
    assert response.url == "/cases"


def test_home_unapproved_staff(client, db):
    user = User.objects.create(email="foo@body")
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


def test_admin_access(staff_user, admin_user, client):
    resp = client.get("/admin/")
    assert "admin/login" in resp.url
    client.force_login(staff_user)
    resp = client.get("/admin/")
    assert "admin/login" in resp.url
    client.force_login(admin_user)
    resp = client.get("/admin/")
    assertContains(resp, "Django site admin")


def test_server_error_page_has_cobrand(rf):
    response = server_error(rf.get("/"))
    assert response.status_code == 500
    assert b"<title>Body Site</title>" in response.content
