import re
import pytest
from pytest_django.asserts import assertContains
from .api import address_for_uprn, addresses_for_postcode

pytestmark = pytest.mark.django_db

ADDRESS = {
    "line1": "LINE 1",
    "line2": "LINE 2",
    "line3": "LINE 3",
    "line4": "",
    "town": "LONDON",
    "postcode": "E8 1DY",
    "UPRN": 10008315925,
    "locality": "LOCALITY",
    "ward": "Hackney Central",
    "longitude": -0.0575203934113829,
    "latitude": 51.5449668465297,
}


@pytest.fixture
def make_api_result():
    def _make_api_result(line3="LINE 3", locality="HACKNEY"):
        output = {
            "data": {
                "address": [ ADDRESS ],
                "page_count": 1,
                "total_count": 1,
            },
            "statusCode": 200,
        }
        output["data"]["address"][0]["line3"] = line3
        output["data"]["address"][0]["locality"] = locality
        return output

    return _make_api_result


def test_with_client(admin_client):
    response = admin_client.get("/cases")
    assertContains(response, "Hackney")


def test_addresses_api_only_outside(requests_mock, make_api_result):
    requests_mock.get(
        re.compile("postcode=E81DY"), json=make_api_result(locality="ELSEWHERE")
    )
    assert len(addresses_for_postcode("E81DY")) == 1


def test_addresses_api(requests_mock, make_api_result):
    requests_mock.get(
        re.compile("postcode=E81DY"), json=make_api_result(line3="HACKNEY")
    )
    assert len(addresses_for_postcode("E81DY")) == 1


def test_addresses_api_uprn_blank(requests_mock):
    requests_mock.get(
        re.compile("uprn=1234"),
        json={
            "data": {"address": [], "page_count": 1, "total_count": 0},
            "statusCode": 200,
        },
    )
    assert address_for_uprn("1234") == {
        "string": "",
        "ward": "",
    }


def test_addresses_api_uprn(requests_mock, make_api_result):
    requests_mock.get(re.compile("uprn=10008315925"), json=make_api_result())
    data = ADDRESS.copy()
    data["string"] = "Line 1, Line 2, Line 3, E8 1DY"
    assert address_for_uprn("10008315925") == data
