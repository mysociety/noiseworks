import re

import pytest

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
def address_lookup(requests_mock):
    requests_mock.get(
        re.compile(r"postcode=E8\+3DY"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(
        re.compile(r"uprn=10008315925"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile(r"greenspaces/ows"), json={"features": []})
    requests_mock.get(re.compile(r"transport/ows"), json={"features": []})
    requests_mock.get(re.compile(r"housing/ows"), json={"features": []})
