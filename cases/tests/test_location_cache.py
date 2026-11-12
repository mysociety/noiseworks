import pytest
from django.contrib.gis.geos import Point

from cobrands.interface import AddressDetail, LocationDetail, PlaceLookupError
from cobrands.testing import TestCobrand

from ..models import Case

pytestmark = pytest.mark.django_db


class TestCobrandWithLookupData(TestCobrand):
    def address_detail_for_uprn(self, uprn):
        if uprn == "ERROR":
            raise PlaceLookupError()
        if uprn == "VALID":
            return AddressDetail(
                label="address label",
                uprn=uprn,
                point=None,
                in_an_estate=None,
                ward_gss="GSS1",
            )
        return None

    def location_detail_for_point(self, point):
        if point.coords[0] == 0:
            raise PlaceLookupError()
        if point.coords[0] == 1:
            return LocationDetail(
                point=point,
                description="location description",
                ward_gss="GSS1",
                in_an_estate=False,
            )
        return None


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.cobrand.with_args(TestCobrandWithLookupData),
]


def test_cache_set_for_uprn():
    c = Case.objects.create(uprn="VALID")
    assert c.location_cache == "address label"


def test_cache_not_set_for_uprn_on_lookup_error():
    c = Case.objects.create(uprn="ERROR")
    assert c.location_cache == ""


def test_cache_not_set_for_uprn_on_no_data_found():
    c = Case.objects.create(uprn="UNKNOWN")
    assert c.location_cache == ""


def test_cache_set_for_point():
    c = Case.objects.create(radius=1, point=Point(1, 0))
    assert c.location_cache == "1m around location description"


def test_cache_not_set_for_point_on_lookup_error():
    c = Case.objects.create(point=Point(0, 0))
    assert c.location_cache == ""


def test_cache_not_set_for_point_on_no_data_found():
    c = Case.objects.create(point=Point(2, 0))
    assert c.location_cache == ""
