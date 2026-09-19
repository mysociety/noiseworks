import pytest
from django.contrib.gis.geos import Point

from ..interface import Cobrand as CobrandInterface
from .cobrand import Cobrand

pytestmark = pytest.mark.django_db

cobrand = Cobrand()


def test_cobrand_implements_cobrand() -> None:
    _: CobrandInterface = cobrand


def test_address_candidates_for_postcode():
    cobrand.address_candidates_for_postcode("POSTCODE")


def test_address_detail_for_uprn():
    cobrand.address_detail_for_uprn("UPRN")


def test_location_candidates_for_string():
    cobrand.location_candidates_for_string("string")


def test_location_detail_for_point():
    cobrand.location_detail_for_point(Point(0, 0, srid=43266))


def test_override_email_colours():
    cobrand.override_email_colours()


def test_override_email_settings():
    cobrand.override_email_settings({})


def test_staff_destination_email_addresses_for_case():
    cobrand.staff_destination_email_addresses_for_case({})
