from pytest_django.asserts import assertContains
from django.conf import settings
from django.http import HttpRequest
from django.utils.module_loading import import_string


def test_with_client(client):
    response = client.get("/")
    assertContains(response, "NoiseWorks")


def test_setting_masking():
    request = HttpRequest()
    request.META = {"DATABASE_URL": "postgis://username:password@host/db"}
    Filter = import_string(settings.DEFAULT_EXCEPTION_REPORTER_FILTER)
    s = Filter().get_safe_request_meta(request)["DATABASE_URL"]
    assert "password" not in s
