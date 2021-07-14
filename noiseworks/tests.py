from pytest_django.asserts import assertContains


def test_with_client(client):
    response = client.get("/")
    assertContains(response, "In progress home page")
    assertContains(
        response, """<meta property="og:url" content="http://testserver/">"""
    )
