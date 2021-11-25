import re
from unittest.mock import patch
import pytest
from pytest_django.asserts import assertContains
from django.contrib.gis.geos import Point
from ..models import Case

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


def test_edit_kind(admin_client):
    case = Case.objects.create(kind="diy", location_cache="preset")
    admin_client.get(f"/cases/{case.id}/edit-kind")
    # Follow so that we fetch the page and get a timeline with the edit in
    admin_client.post(f"/cases/{case.id}/edit-kind", {"kind": "music"}, follow=True)


@pytest.fixture
def form_defaults():
    return {
        "where": "residence",
        "estate": "?",
        "radius": "800",
        "point": "SRID=27700;POINT (470267 122766)",
    }


def test_edit_location(requests_mock, admin_client, form_defaults):
    requests_mock.get(re.compile("postcode=BAD"), json={})
    requests_mock.get(
        re.compile("postcode=SW1A1AA"),
        json={"data": {"address": [{**ADDRESS, "locality": "WESTMINSTER"}]}},
    )
    requests_mock.get(
        re.compile("greenspaces/ows"),
        json={
            "features": [
                {
                    "type": "Feature",
                    "id": "hackney_park.1",
                    "properties": {
                        "park_id": "P37",
                        "name": "Shepherdess Walk",
                        "new_ward": "Hoxton West",
                    },
                }
            ]
        },
    )

    case = Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)
    assert case.location_display == "800m around a point in Shepherdess Walk"

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


def test_edit_location_to_uprn(requests_mock, admin_client, form_defaults):
    requests_mock.get(
        re.compile("postcode=E95RF"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(
        re.compile("uprn=10008315925"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile("greenspaces/ows"), json={"features": []})
    # Mock a road
    requests_mock.get(
        re.compile("transport/ows"),
        json={
            "features": [
                {
                    "type": "Feature",
                    "id": "os_highways_street.1695",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [
                            [
                                [533338, 182414],
                                [533337, 182440],
                                [533337, 182440],
                                [533337, 182459],
                            ]
                        ],
                    },
                    "properties": {
                        "usrn": 20900732,
                        "authority_name": "Hackeny",
                        "name": "NEW INN STREET",
                    },
                },
                {
                    "type": "Feature",
                    "id": "os_highways_street.1695",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [533338, 182414],
                            [533337, 182440],
                            [533337, 182440],
                            [533337, 182459],
                        ],
                    },
                    "properties": {
                        "usrn": 20900732,
                        "authority_name": "Hackeny",
                        "name": "NEW INN STREET",
                    },
                },
                {
                    "type": "Feature",
                    "id": "os_highways_street.1695",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [533338, 182414],
                    },
                    "properties": {
                        "usrn": 20900732,
                        "authority_name": "Hackeny",
                        "name": "NEW INN STREET",
                    },
                },
            ]
        },
    )

    case = Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)
    assert (
        case.location_display
        == "800m around a point near New Inn Street / New Inn Street"
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
    case = Case.objects.get(id=case.id)
    assert case.location_display == "Line 1, Line 2, Line 3, E8 1DY"
    assert case.uprn == "10008315925"
