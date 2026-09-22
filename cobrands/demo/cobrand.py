import csv
import random
import re
from email.utils import make_msgid
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import Point

from noiseworks.sass import inline_image_html

from ..hackney.cobrand import Cobrand as HackneyCobrand
from ..interface import (
    AddressCandidate,
    AddressDetail,
    LocationCandidate,
    LocationDetail,
)

hackney_cobrand = HackneyCobrand()

# See the 'generate_addresses' command.
ADDRESS_FILE = Path(__file__).resolve().parent / "addresses.csv"


@cache
def addresses() -> List[Dict[str, str]]:
    with ADDRESS_FILE.open() as f:
        return list(csv.DictReader(f))


def _normalize_pc(pc):
    return re.sub("[^A-Z0-9]", "", pc.upper())


class Cobrand:
    body_name = "Council"
    site_name = "EnviroWorks"
    page_title_suffix = "EnviroWorks"
    staff_email_domains = ["societyworks", "mysociety"]
    wards = hackney_cobrand.wards
    reporting_kind_form_help_text: Optional[str] = None
    map_tile_url: Optional[str] = None

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        return [
            AddressCandidate(uprn=row["uprn"], label=row["label"])
            for row in addresses()
            if _normalize_pc(row["postcode"]) == (_normalize_pc(postcode))
        ]

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        for row in addresses():
            if row["uprn"] == uprn:
                return AddressDetail(
                    uprn=uprn,
                    label=f"{row['label']}, {row['postcode']}",
                    point=Point(
                        float(row["easting"]), float(row["northing"]), srid=27700
                    ),
                    ward_gss=row["ward_gss"],
                    in_an_estate=None,
                )
        return None

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        return hackney_cobrand.location_candidates_for_string(string)

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        ward = "outside"
        key = settings.MAPIT_API_KEY
        data = requests.get(
            f"https://mapit.mysociety.org/point/27700/{point.x},{point.y}?api_key={key}"
        ).json()
        if "2508" in data.keys():
            for area in data.values():
                if area["type"] == "LBW":
                    ward = area["codes"]["gss"]

        near_thing = random.choice(
            [
                "in Haggerston Park",
                "in Hackney Marshes",
                "in London Fields",
                "in Springfield Park",
                "near Bellfast Road",
                "near Clissold Crescent",
                "near Frampton Park Road",
                "near Grove Road",
                "near Glyn Road",
                "near Palatine Road",
                "near Stamford Hill",
                "near Wick Road",
            ]
        )
        return LocationDetail(
            point=point,
            description=f"a point {near_thing}",
            ward_gss=ward,
            in_an_estate=None,
        )

    def example_uprns(self) -> List[str]:
        return [row["uprn"] for row in addresses()]

    def staff_destination_email_addresses_for_case(self, case) -> List[str]:
        return ["staff-dest@example.org"]

    def override_email_colours(self) -> dict:
        color_black = "#000000"
        color_white = "#FFFFFF"
        color_purple = "#7B60B6"
        color_purple_dark = "#624D92"
        color_purple_pale = "#F4F1F9"

        body_background_color = color_purple_pale
        body_text_color = color_black
        header_background_color = color_purple
        header_text_color = color_white
        secondary_column_background_color = color_white
        button_background_color = color_purple_dark
        button_text_color = color_white

        logo_width = "200"  # pixel measurement, but without 'px' suffix
        logo_height = "45"  # pixel measurement, but without 'px' suffix
        logo_inline = {
            "id": make_msgid(domain="example.org")[1:-1],
            "data": inline_image_html("enviroworks-logo-white.png"),
        }
        header_padding = "20px 30px"

        return locals()

    def override_email_settings(self, settings: dict) -> dict:
        return {}
