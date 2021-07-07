from pytest_django.asserts import assertContains


def test_with_client(client):
    response = client.get("/")
    assertContains(response, "In progress home page")
