import re
from io import StringIO
from django.core.management import call_command, CommandError
import pytest


@pytest.fixture
def call_params(db):
    call_command("loaddata", "action_types", stdout=StringIO())
    uprns = "1\n2\n3\n4"
    return {
        "uprns": StringIO(uprns),
        "fixed": True,
        "stdout": StringIO(),
    }


@pytest.fixture
def mock_things(requests_mock):
    requests_mock.get(
        re.compile("uprn=[1-3]"),
        json={
            "data": {
                "address": [
                    {
                        "line1": "LINE 1",
                        "line2": "LINE 2",
                        "line3": "LINE 3",
                        "postcode": "E8 1DY",
                        "ward": "Hackney Central",
                        "latitude": 51.5449668465297,
                        "longitude": -0.0575203934113829,
                    }
                ]
            }
        },
    )
    requests_mock.get(
        re.compile("uprn=4"),
        json={"data": {"address": []}},
    )
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={
            "2508": {"type": "LBO"},
            "144397": {"type": "LBW", "codes": {"gss": "E05009385"}},
        },
    )
    requests_mock.get(re.compile("greenspaces/ows"), json={"features": []})
    requests_mock.get(re.compile("transport/ows"), json={"features": []})


def test_random_command_bad_input(db):
    with pytest.raises(CommandError):
        call_command("add_random_cases")
    with pytest.raises(CommandError):
        call_command("add_random_cases", uprns=StringIO())


def test_random_command_no_mapit(requests_mock, mock_things, db, call_params):
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={"error": "There was an error"},
    )
    with pytest.raises(Exception) as excinfo:
        call_command("add_random_cases", number=1, **call_params)
    assert "Error calling MapIt" == str(excinfo.value)


def test_random_command(mock_things, db, call_params):
    # Calling without commit does still save some things to the database at present
    call_command("add_random_cases", number=11, **call_params)


def test_random_command_commit(mock_things, db, call_params):
    # 70 is enough for the fixed random seed to return all possible values
    call_command("add_random_cases", number=70, commit=True, **call_params)
