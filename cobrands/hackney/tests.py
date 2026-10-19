import re
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point

from cases.models import Case

from ..interface import AddressCandidate
from ..interface import Cobrand as CobrandInterface
from ..interface import PlaceLookupError
from .cobrand import Cobrand

pytestmark = pytest.mark.django_db

cobrand = Cobrand()


def test_cobrand_implements_cobrand() -> None:
    _: CobrandInterface = cobrand


def test_query_address_api_raises_place_lookup_error_on_invalid_or_missing_data(
    requests_mock,
):
    requests_mock.get(re.compile("postcode=E81DY"), text="not json!")
    with pytest.raises(PlaceLookupError) as e:
        cobrand._query_address_api({"postcode": "E81DY"})

    # No data field.
    requests_mock.get(re.compile("postcode=E81DY"), json={})
    with pytest.raises(PlaceLookupError) as e:
        cobrand._query_address_api({"postcode": "E81DY"})

    requests_mock.get(re.compile("postcode=E81DY"), status_code=503)
    with pytest.raises(PlaceLookupError) as e:
        cobrand._query_address_api({"postcode": "E81DY"})


def test_query_address_api_returns_no_data_on_400(requests_mock):
    requests_mock.get(re.compile("postcode=E81DY"), status_code=400)
    data = cobrand._query_address_api({"postcode": "E81DY"})
    assert data is None


def test_wfs_lookups_handle_server_being_down(requests_mock):
    requests_mock.get(re.compile("typename=test"), text="error")
    cobrand._wfs_lookup("url", "test")


def test_address_candidates_for_postcode_ignores_outside_results_and_400s(
    requests_mock, make_address_api_result
):
    requests_mock.get(
        re.compile("postcode=E81DY"), json=make_address_api_result(gazetteer="National")
    )
    assert cobrand.address_candidates_for_postcode("E81DY") == []

    requests_mock.get(
        re.compile("postcode=E81DY"), json=make_address_api_result(outof=True)
    )
    assert cobrand.address_candidates_for_postcode("E81DY") == []

    requests_mock.get(re.compile("postcode=E81DY"), status_code=400)
    assert cobrand.address_candidates_for_postcode("E81DY") == []


ADDRESS = {
    "line1": "LINE 1",
    "line2": "LINE 2",
    "line3": "LINE 3",
    "line4": "",
    "town": "LONDON",
    "postcode": "E8 1DY",
    "UPRN": 10008315925,
    "locality": "",
    "gazetteer": "Gazetteer",
    "outOfBoroughAddress": False,
    "ward": "Hackney Central",
    "longitude": -0.0575203934113829,
    "latitude": 51.5449668465297,
}


@pytest.fixture
def make_address_api_result():
    def _make_api_result(line3="LINE 3", gazetteer="Hackney", outof=None):
        output = {
            "data": {
                "address": [ADDRESS],
                "page_count": 1,
                "total_count": 1,
            },
            "statusCode": 200,
        }
        output["data"]["address"][0]["line3"] = line3
        if outof is None:
            if "outOfBoroughAddress" in output["data"]["address"][0]:
                del output["data"]["address"][0]["outOfBoroughAddress"]
        else:
            output["data"]["address"][0]["outOfBoroughAddress"] = outof
        output["data"]["address"][0]["gazetteer"] = gazetteer
        return output

    return _make_api_result


def test_address_candidates_for_postcode(requests_mock, make_address_api_result):
    requests_mock.get(re.compile("postcode=E81DY"), json=make_address_api_result())
    candidates = cobrand.address_candidates_for_postcode("E81DY")
    assert len(candidates) == 1
    assert candidates[0] == AddressCandidate(
        uprn=10008315925, label="Line 1, Line 2, Line 3"
    )


def test_address_detail_for_uprn_empty_on_no_results(requests_mock):
    requests_mock.get(re.compile("uprn=10008315925"), json={"data": {"address": []}})
    details = cobrand.address_detail_for_uprn("10008315925")
    assert details is None


def test_address_detail_for_uprn(requests_mock, make_address_api_result):
    requests_mock.get(re.compile("uprn=10008315925"), json=make_address_api_result())
    requests_mock.get(
        re.compile("housing/ows"), json={"features": [{"properties": "estate"}]}
    )
    details = cobrand.address_detail_for_uprn("10008315925")

    assert details is not None
    assert details.label == "Line 1, Line 2, Line 3, E8 1DY"
    assert details.ward_gss == "E05009372"
    assert details.in_an_estate


def test_location_candidates_for_string_raises_exception_request_failure(requests_mock):
    requests_mock.get(
        re.compile("search"),
        status_code=503,
    )
    with pytest.raises(PlaceLookupError) as e:
        cobrand.location_candidates_for_string("woodberry down")


def test_location_candidates_for_string(requests_mock):
    display_name = (
        "Woodberry Down, "
        "Stoke Newington, "
        "London Borough of Hackney, "
        "Greater London, "
        "England, "
        "N4 1QR, "
        "United Kingdom"
    )
    requests_mock.get(
        re.compile("openstreetmap"),
        json=[
            {
                "display_name": display_name,
                "lat": "51.5724915",
                "lon": "-0.0906990",
            },
            {
                "display_name": "North Pole",
                "lat": "90",
                "lon": "0",
            },
        ],
    )
    candidates = cobrand.location_candidates_for_string("woodberry down")
    assert len(candidates) == 1
    assert candidates[0].label == (
        "Woodberry Down, Stoke Newington, Greater London, England, N4 1QR"
    )


def test_location_detail_for_point(requests_mock):
    requests_mock.get(re.compile("greenspaces/ows"), json={})
    requests_mock.get(re.compile("transport/ows"), json={})
    requests_mock.get(
        re.compile("housing/ows"), json={"features": [{"properties": "estate"}]}
    )
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={
            "2508": {"type": "LBO"},
            "144397": {"type": "LBW", "codes": {"gss": "E05009385"}},
        },
    )
    details = cobrand.location_detail_for_point(Point(532414, 187685, srid=27700))
    assert details is not None
    assert details.description == "(532414,187685)"
    assert details.ward_gss == "E05009385"
    assert details.in_an_estate

    requests_mock.get(
        re.compile("transport/ows"),
        json={
            "features": [
                {
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [
                            [
                                [532413, 187685],
                                [532414, 187685],
                                [532415, 187685],
                                [532415, 187685],
                            ]
                        ],
                    },
                    "properties": {
                        "name": "Closer Road",
                    },
                },
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [532413, 187686],
                            [532414, 187686],
                            [532415, 187686],
                        ],
                    },
                    "properties": {
                        "name": "Further Road",
                    },
                },
                {
                    "geometry": {
                        "type": "Point",
                        "coordinates": [532419, 187689],
                    },
                    "properties": {
                        "name": "Point Further Out",
                    },
                },
            ]
        },
    )

    details = cobrand.location_detail_for_point(Point(532414, 187685, srid=27700))
    assert details is not None
    assert details.description == "a point near Further Road / Closer Road"

    requests_mock.get(
        re.compile("greenspaces/ows"),
        json={"features": [{"properties": {"name": "park"}}]},
    )
    details = cobrand.location_detail_for_point(Point(532414, 187685, srid=27700))
    assert details is not None
    assert details.description == "a point in park"


def test_staff_destination_email_addresses_for_case(settings):
    settings.COBRAND_SETTINGS["staff_destination"] = {
        "outside": "outside@example.org",
        "business": "business@example.org",
        "hackney-housing": "hh@example.org,hh2@example.org",
        "housing": "housing@example.org",
    }
    assert cobrand.staff_destination_email_addresses_for_case(
        Case.objects.create(ward="outside")
    ) == ["outside@example.org"]
    assert cobrand.staff_destination_email_addresses_for_case(
        Case.objects.create(where="business")
    ) == ["business@example.org"]
    assert cobrand.staff_destination_email_addresses_for_case(
        Case.objects.create(estate="y")
    ) == ["hh@example.org", "hh2@example.org"]
    assert cobrand.staff_destination_email_addresses_for_case(
        Case.objects.create()
    ) == ["housing@example.org"]


def test_example_uprns():
    assert cobrand.example_uprns() == []


def test_override_email_colours():
    # The logo is only on the static path when the demo cobrand is installed.
    with patch("cobrands.demo.cobrand.inline_image_html", return_value=b"logo"):
        cobrand.override_email_colours()


def test_override_email_settings():
    cobrand.override_email_settings(
        {
            "only_column_style": "",
            "column_divider_color": "",
            "primary_column_style": "",
            "secondary_column_background_color": "",
            "secondary_column_text_color": "",
        }
    )
