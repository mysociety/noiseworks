import csv
import json
import re
from io import StringIO

import pytest
from django.contrib.gis.geos import Polygon
from django.core.management import call_command
from django.core.management.base import CommandError

from cases.forms.reporting import canonical_postcode

from .cobrand import Cobrand
from .management.commands import generate_addresses
from .management.commands.generate_addresses import Command

BOUNDARY = Polygon.from_bbox((-0.0605, 51.5495, -0.0595, 51.5505))
BOUNDARY.srid = 4326


@pytest.fixture(autouse=True)
def mapit(requests_mock):
    requests_mock.get(re.compile("mapit.mysociety.org/code/gss/"), json={"id": 1})
    requests_mock.get(
        re.compile(r"mapit.mysociety.org/area/1.geojson"),
        json=json.loads(BOUNDARY.json),
    )


def generate(tmp_path, **options):
    path = tmp_path / "addresses.csv"
    call_command(Command(), output=str(path), stdout=StringIO(), **options)
    with path.open() as f:
        return path.read_text(), list(csv.DictReader(f))


def test_generates_addresses(tmp_path):
    _, rows = generate(tmp_path, number=40)
    assert len(rows) == 40


def test_sample_attempts_run_out(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_addresses, "SAMPLE_ATTEMPTS", 0)
    with pytest.raises(CommandError):
        generate(tmp_path, number=1)
