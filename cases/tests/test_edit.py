import datetime
import re
from http import HTTPStatus

import pytest
from django.contrib.gis.geos import Point
from pytest_django.asserts import assertContains

from cobrands.interface import (
    AddressCandidate,
    AddressDetail,
    LocationDetail,
    PlaceLookupError,
)
from cobrands.testing import TestCobrand

from ..models import Case

pytestmark = pytest.mark.django_db


def test_edit_kind(admin_client):
    case = Case.objects.create(kind="diy", location_cache="preset")
    admin_client.get(f"/cases/{case.id}/edit-kind")
    # Follow so that we fetch the page and get a timeline with the edit in
    admin_client.post(f"/cases/{case.id}/edit-kind", {"kind": "music"}, follow=True)


def test_edit_kind_other(admin_client):
    case = Case.objects.create(kind="diy", location_cache="preset")
    resp = admin_client.post(
        f"/cases/{case.id}/edit-kind",
        {"kind": "other", "kind_other": "<script>hello</script>"},
        follow=True,
    )
    assertContains(resp, "from  to &lt;")


@pytest.fixture
def form_defaults():
    return {
        "where": "residence",
        "estate": "?",
        "radius": "800",
        "point": "SRID=27700;POINT (470267 122766)",
    }


class TestCobrandWithLookupData(TestCobrand):
    def address_candidates_for_postcode(self, postcode):
        if postcode == "ERROR":
            raise PlaceLookupError()
        elif postcode == "VALID":
            return [
                AddressCandidate(
                    uprn="1001",
                    label="label",
                )
            ]
        return []

    def address_detail_for_uprn(self, uprn):
        return AddressDetail(
            label="label", uprn=uprn, point=None, in_an_estate=None, ward_gss="GSS1"
        )

    def location_detail_for_point(self, point):
        return LocationDetail(
            point=point,
            description="description",
            ward_gss="GSS1",
            in_an_estate=False,
        )


@pytest.mark.cobrand.with_args(TestCobrandWithLookupData)
def test_edit_location(admin_client, form_defaults):
    case = Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)
    assert case.location_display == "800m around description"

    admin_client.get(f"/cases/{case.id}/edit-location")

    # Post with no changes
    resp = admin_client.post(f"/cases/{case.id}/edit-location", form_defaults)
    # Post and get an error
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "ERROR"},
    )
    assertContains(resp, "something went wrong")
    # Post with an outside postcode
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "UNKNOWN"},
    )
    assertContains(resp, "could not recognise that postcode")


@pytest.mark.cobrand.with_args(TestCobrandWithLookupData)
def test_edit_location_to_uprn(admin_client, form_defaults):
    case = Case.objects.create(kind="diy", point=Point(470267, 122766), radius=800)
    assert case.location_display == "800m around description"

    # Post with a postcode
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "VALID"},
    )
    assertContains(resp, 'value="1001"')
    # Post with a UPRN
    resp = admin_client.post(
        f"/cases/{case.id}/edit-location",
        {**form_defaults, "postcode": "VALID", "addresses": "1001"},
    )
    case = Case.objects.get(id=case.id)
    assert case.location_display == "label"
    assert case.uprn == "1001"


def test_edit_priority(admin_client):
    case = Case.objects.create(kind="diy", location_cache="preset", priority=False)
    admin_client.post(
        f"/cases/{case.id}/priority",
        {"priority": True},
    )
    case.refresh_from_db()
    assert case.priority
    admin_client.post(
        f"/cases/{case.id}/priority",
        {"priority": False},
    )
    case.refresh_from_db()
    assert not case.priority


def test_edit_review_date(admin_client):
    case = Case.objects.create(kind="diy", location_cache="preset", review_date=None)

    response = admin_client.get(f"/cases/{case.id}/edit-review-date")
    assert response.status_code == HTTPStatus.OK

    admin_client.post(
        f"/cases/{case.id}/edit-review-date",
        {
            "has_review_date": True,
            "review_date_0": "12",
            "review_date_1": "10",
            "review_date_2": "2022",
        },
    )
    case.refresh_from_db()
    assert case.review_date == datetime.date(2022, 10, 12)

    admin_client.post(
        f"/cases/{case.id}/edit-review-date",
        {
            "has_review_date": False,
            "review_date_0": "12",
            "review_date_1": "10",
            "review_date_2": "2022",
        },
    )
    case.refresh_from_db()
    assert case.review_date == None
