import re
from unittest.mock import patch
import pytest
from pytest_django.asserts import assertContains
from django.contrib.gis.geos import Point
from .models import Case

pytestmark = pytest.mark.django_db

ADDRESS = {
    "line1": "LINE 1",
    "line2": "LINE 2",
    "line3": "LINE 3",
    "line4": "",
    "town": "LONDON",
    "postcode": "E8 1DY",
    "UPRN": 10008315925,
    "locality": "HACKNEY",
    "ward": "Hackney Central",
    "longitude": -0.0575203934113829,
    "latitude": 51.5449668465297,
}


@pytest.fixture
def case(db):
    return Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)


def test_edit_kind(admin_client, case):
    admin_client.get(f"/cases/{case.id}/edit-kind")
    admin_client.post(f"/cases/{case.id}/edit-kind", {"kind": "music"})


@pytest.fixture
def form_defaults():
    return {
        "where": "residence",
        "estate": "?",
        "radius": "800",
        "point": "SRID=27700;POINT (470267 122766)",
    }


def test_edit_location(requests_mock, admin_client, case, form_defaults):
    requests_mock.get(re.compile("postcode=BAD"), json={})
    requests_mock.get(
        re.compile("postcode=SW1A1AA"),
        json={"data": {"address": [{**ADDRESS, "locality": "WESTMINSTER"}]}},
    )

    admin_client.get(f"/cases/{case.id}/edit-location")

    # Post with no changes
    resp = admin_client.post(f"/cases/{case.id}/edit-location", form_defaults)
    # Post with a bad postcode
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "BAD"},
    )
    # Post with an outside postcode
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "SW1A1AA"},
    )
    assertContains(resp, "could not recognise that postcode")


def test_edit_location_to_uprn(requests_mock, admin_client, case, form_defaults):
    requests_mock.get(
        re.compile("postcode=E95RF"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(
        re.compile("uprn=10008315925"), json={"data": {"address": [ADDRESS]}}
    )

    # Post with a postcode
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "E95RF"},
    )
    assertContains(resp, 'value="10008315925"')
    # Post with a UPRN
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "E95RF", "addresses": "10008315925"},
    )
    case.refresh_from_db()
    assert case.location_display == "Line 1, Line 2, Line 3, E8 1DY"
    assert case.uprn == "10008315925"
