import csv
import json
import random

import requests
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management.base import BaseCommand, CommandError

from ...cobrand import ADDRESS_FILE, Cobrand

MAPIT_URL = "https://mapit.mysociety.org"

OUTWARD_CODES = ["E2", "E5", "E8", "E9", "N1", "N16"]
INWARD_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"

FIRST_UPRN = 9000000001

STREET_NAMES = [
    "Albion",
    "Barbauld",
    "Bellfast",
    "Brooksby",
    "Cazenove",
    "Chatsworth",
    "Clapton",
    "Clissold",
    "Dalston",
    "Digby",
    "Frampton",
    "Gascoyne",
    "Glyn",
    "Graham",
    "Haggerston",
    "Homerton",
    "Kenninghall",
    "Lauriston",
    "Lea Bridge",
    "Millfields",
    "Mursell",
    "Navarino",
    "Northwold",
    "Palatine",
    "Pembury",
    "Powerscroft",
    "Rendlesham",
    "Rushmore",
    "Shacklewell",
    "Southwold",
    "Springfield",
    "Stoke Newington",
    "Sylvester",
    "Wilton",
    "Woodberry",
]
STREET_TYPES = ["Road", "Street", "Lane", "Gardens", "Terrace", "Walk", "Crescent"]

ADDRESSES_PER_STREET = 12
# We use ward boundary extents to generate a point so it's possible
# we generates ones that aren't actually inside the ward (the ward is probably
# not a perfect square.).
# Try this many times before giving up.
SAMPLE_ATTEMPTS = 100


class Command(BaseCommand):
    help = "Generate the demo cobrand's file of made-up addresses"

    def add_arguments(self, parser):
        parser.add_argument(
            "--number", help="How many addresses to generate", type=int, default=500
        ),
        parser.add_argument("--seed", type=str, default="demo")
        parser.add_argument("--output", help="Where to write", default=ADDRESS_FILE)

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        wards = Cobrand.wards
        names = self.street_names(rng)
        created = 0

        print(f"number: {options['number']}")
        rows = []
        for i, ward in enumerate(wards):
            boundary = self.ward_boundary(ward.gss_code)

            # Share the addresses out, giving the remainder to the first wards.
            wanted = options["number"] // len(wards)
            if i < options["number"] % len(wards):
                wanted += 1

            while wanted > 0:
                street = names.pop()
                postcode = self.postcode(rng)
                addresses = min(wanted, ADDRESSES_PER_STREET)
                for number in range(1, addresses + 1):
                    point = self.point_inside(rng, boundary)
                    rows.append(
                        {
                            "uprn": FIRST_UPRN + len(rows),
                            "label": f"{number} {street}",
                            "postcode": postcode,
                            "easting": round(point.x),
                            "northing": round(point.y),
                            "ward_gss": ward.gss_code,
                        }
                    )
                    created += 1
                    wanted -= 1

        with open(options["output"], "w") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(f"Wrote {len(rows)} addresses to {options['output']}")

    def street_names(self, rng):
        names = [f"{name} {type}" for name in STREET_NAMES for type in STREET_TYPES]
        rng.shuffle(names)
        return names

    def postcode(self, rng):
        inward = "".join(rng.choice(INWARD_LETTERS) for _ in range(2))
        return f"{rng.choice(OUTWARD_CODES)} {rng.randint(1, 9)}{inward}"

    def ward_boundary(self, gss_code):
        params = {"api_key": settings.MAPIT_API_KEY}
        area = requests.get(f"{MAPIT_URL}/code/gss/{gss_code}", params=params)
        area.raise_for_status()
        geojson = requests.get(
            f"{MAPIT_URL}/area/{area.json()['id']}.geojson", params=params
        )
        geojson.raise_for_status()
        boundary = GEOSGeometry(json.dumps(geojson.json()), srid=4326)
        boundary.transform(27700)
        return boundary

    def point_inside(self, rng, boundary):
        min_x, min_y, max_x, max_y = boundary.extent
        for _ in range(SAMPLE_ATTEMPTS):
            point = Point(
                rng.uniform(min_x, max_x), rng.uniform(min_y, max_y), srid=27700
            )
            if boundary.contains(point):
                return point
        raise CommandError(f"Could not find a point inside {boundary}")
