import pytest
from pytest_django.asserts import assertContains

pytestmark = pytest.mark.django_db


def test_with_client(admin_client):
    response = admin_client.get("/cases")
    assertContains(response, "Hackney")
