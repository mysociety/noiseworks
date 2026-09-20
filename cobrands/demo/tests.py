import csv
import re
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point

from ..interface import Cobrand as CobrandInterface
from ..interface import LocationCandidate
from . import cobrand as cobrand_module
from .cobrand import Cobrand

pytestmark = pytest.mark.django_db

cobrand = Cobrand()

ADDRESSES = [
    (
        "9000000001",
        "1 Bellfast Road",
        "E8 1DY",
        533500,
        184600,
        "E05009372",
    ),
    (
        "9000000002",
        "2 Bellfast Road",
        "E8 1DY",
        533520,
        184620,
        "E05009372",
    ),
    ("9000000003", "1 Glyn Road", "E9 5DA", 535000, 185000, "E05009376"),
]


@pytest.fixture(autouse=True)
def address_file(tmp_path, monkeypatch):
    path = tmp_path / "addresses.csv"
    with path.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["uprn", "label", "postcode", "easting", "northing", "ward_gss"]
        )
        writer.writerows(ADDRESSES)
    monkeypatch.setattr(cobrand_module, "ADDRESS_FILE", path)
    cobrand_module.addresses.cache_clear()
    yield
    cobrand_module.addresses.cache_clear()


def test_cobrand_implements_cobrand() -> None:
    _: CobrandInterface = cobrand


def test_address_candidates_for_postcode():
    candidates = cobrand.address_candidates_for_postcode("E8 1DY")
    assert [(c.uprn, c.label) for c in candidates] == [
        ("9000000001", "1 Bellfast Road"),
        ("9000000002", "2 Bellfast Road"),
    ]


def test_address_candidates_for_unknown_postcode():
    assert cobrand.address_candidates_for_postcode("E8 9ZZ") == []


def test_address_detail_for_uprn():
    details = cobrand.address_detail_for_uprn("9000000003")
    assert details.label == "1 Glyn Road, E9 5DA"
    assert details.ward_gss == "E05009376"
    assert details.in_an_estate is None
    assert details.point.srid == 27700
    assert details.point.coords == (535000, 185000)


def test_address_detail_for_unknown_uprn():
    assert cobrand.address_detail_for_uprn("1234") is None


def test_location_candidates_for_string():
    with patch("cobrands.hackney.cobrand.Cobrand.location_candidates_for_string") as m:
        m.return_value = [
            LocationCandidate(label="label", point=Point(0, 0, srid=27700))
        ]
        candidates = cobrand.location_candidates_for_string("string")
    assert candidates[0].label == "label"


def test_location_detail_for_point(requests_mock):
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={
            "2508": {"type": "LBO"},
            "144397": {"type": "LBW", "codes": {"gss": "E05009376"}},
        },
    )
    details = cobrand.location_detail_for_point(Point(535000, 185000, srid=27700))
    assert details.ward_gss == "E05009376"
    assert details.description.startswith("a point ")
    assert details.in_an_estate is None


def test_location_detail_for_point():
    cobrand.location_detail_for_point(Point(0, 0, srid=43266))


def test_override_email_colours():
    cobrand.override_email_colours()


def test_override_email_settings():
    cobrand.override_email_settings({})


def test_staff_destination_email_addresses_for_case():
    cobrand.staff_destination_email_addresses_for_case({})
